"""Lineage resolution - maps ETL/FK references to catalog assets across ALL connectors.

Script references (e.g. 'shop.orders', 'project.dataset.table', 'customers') are resolved
against a qualified-name index built from every asset's external_id + name, with a
confidence score, so the same bare name in different systems doesn't get mis-linked.
"""
from __future__ import annotations

import re
import uuid
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets import Asset
from app.models.lineage import LineageEdge

_SPLIT = re.compile(r"[./]")


def _segments(identifier: str) -> list[str]:
    cleaned = identifier.strip().strip('`"[]').lower().replace("s3://", "").replace("repo://", "")
    return [p for p in _SPLIT.split(cleaned) if p]


def build_match_index(assets: Iterable[Tuple[uuid.UUID, str, str]]) -> dict:
    """assets = iterable of (id, name, external_id). Returns a multi-key index."""
    exact: Dict[str, uuid.UUID] = {}
    qualified: Dict[str, set] = {}
    by_name: Dict[str, set] = {}
    for aid, name, ext in assets:
        if ext:
            exact[ext.strip().lower()] = aid
            segs = _segments(ext)
            for k in range(1, min(3, len(segs)) + 1):
                qualified.setdefault(".".join(segs[-k:]), set()).add(aid)
        if name:
            by_name.setdefault(name.strip().lower(), set()).add(aid)
    return {"exact": exact, "qualified": qualified, "by_name": by_name}


def resolve_ref(ref: str, index: dict) -> Optional[Tuple[uuid.UUID, float]]:
    """Resolve a script reference to (asset_id, confidence) or None."""
    if not ref:
        return None
    r = ref.strip().strip('`"[]').lower()
    if r in index["exact"]:
        return index["exact"][r], 1.0
    segs = _segments(ref)
    if not segs:
        return None
    # longest qualified suffix that is unambiguous wins
    for k in range(min(3, len(segs)), 0, -1):
        key = ".".join(segs[-k:])
        hit = index["qualified"].get(key)
        if hit and len(hit) == 1:
            return next(iter(hit)), 0.9 if k > 1 else 0.75
    name = segs[-1]
    hit = index["by_name"].get(name)
    if hit:
        return next(iter(hit)), 0.7 if len(hit) == 1 else 0.4
    return None


class LineageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _index(self, org_id: uuid.UUID) -> dict:
        rows = (await self.db.execute(
            select(Asset.id, Asset.name, Asset.external_id).where(Asset.org_id == org_id)
        )).all()
        return build_match_index((r[0], r[1], r[2]) for r in rows)

    async def _edge_exists(self, sid, tid, transform_id) -> bool:
        return (await self.db.execute(
            select(LineageEdge.id).where(
                LineageEdge.source_asset_id == sid, LineageEdge.target_asset_id == tid,
                LineageEdge.transformation_asset_id == transform_id)
        )).scalar_one_or_none() is not None

    async def _apply_edges(self, org_id, transform_id, edges, index, lineage_type="table") -> int:
        created = 0
        for e in edges or []:
            for s in e.get("sources", []) or []:
                for t in e.get("targets", []) or []:
                    sm, tm = resolve_ref(str(s), index), resolve_ref(str(t), index)
                    if not sm or not tm or sm[0] == tm[0]:
                        continue
                    if await self._edge_exists(sm[0], tm[0], transform_id):
                        continue
                    self.db.add(LineageEdge(
                        org_id=org_id, source_asset_id=sm[0], target_asset_id=tm[0],
                        transformation_asset_id=transform_id, lineage_type=lineage_type,
                        transformation_logic=e.get("transformation_file"),
                        confidence_score=round(min(sm[1], tm[1]), 2)))
                    created += 1
        await self.db.flush()
        return created

    async def _apply_column_edges(self, org_id, transform_id, col_edges, index) -> int:
        created = 0
        for e in col_edges or []:
            s_ref = f"{e.get('source_table')}.{e.get('source_column')}"
            t_ref = f"{e.get('target_table')}.{e.get('target_column')}"
            sm, tm = resolve_ref(s_ref, index), resolve_ref(t_ref, index)
            if not sm or not tm or sm[0] == tm[0]:
                continue
            if await self._edge_exists(sm[0], tm[0], transform_id):
                continue
            self.db.add(LineageEdge(
                org_id=org_id, source_asset_id=sm[0], target_asset_id=tm[0],
                transformation_asset_id=transform_id, lineage_type="column",
                transformation_logic=e.get("transformation_file"),
                confidence_score=round(min(sm[1], tm[1]), 2)))
            created += 1
        await self.db.flush()
        return created

    async def rebuild_org_lineage(self, org_id: uuid.UUID) -> dict:
        """Re-resolve every asset's stored lineage_edges against the current catalog."""
        index = await self._index(org_id)
        assets = (await self.db.execute(
            select(Asset).where(Asset.org_id == org_id,
                                Asset.asset_type == "etl_pipeline"))).scalars().all()
        created = 0
        pipelines = 0
        for a in assets:
            md = a.technical_metadata or {}
            t_edges = md.get("lineage_edges") or []
            c_edges = md.get("column_lineage_edges") or []
            if not t_edges and not c_edges:
                continue
            pipelines += 1
            created += await self._apply_edges(org_id, a.id, t_edges, index, "table")
            created += await self._apply_column_edges(org_id, a.id, c_edges, index)
        return {"assets_with_lineage": pipelines, "edges_created": created}

    async def graph(self, org_id: uuid.UUID, level: str = "table") -> dict:
        stmt = select(LineageEdge).where(LineageEdge.org_id == org_id)
        if level == "column":
            stmt = stmt.where(LineageEdge.lineage_type == "column")
        else:
            stmt = stmt.where(LineageEdge.lineage_type != "column")
        edges = (await self.db.execute(stmt)).scalars().all()
        node_ids = set()
        for e in edges:
            node_ids.add(e.source_asset_id)
            node_ids.add(e.target_asset_id)
        nodes = []
        if node_ids:
            rows = (await self.db.execute(select(Asset).where(Asset.id.in_(node_ids)))).scalars().all()
            nodes = [{"id": str(a.id), "name": a.name, "asset_type": a.asset_type,
                      "external_id": a.external_id, "sensitivity_level": a.sensitivity_level}
                     for a in rows]
        return {"nodes": nodes,
                "edges": [{"id": str(e.id), "source": str(e.source_asset_id),
                           "target": str(e.target_asset_id), "transformation": e.transformation_logic,
                           "confidence": e.confidence_score} for e in edges]}
