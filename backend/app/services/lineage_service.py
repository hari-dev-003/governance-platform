"""Lineage service — turns connector-reported raw lineage into edges."""
from __future__ import annotations

import uuid
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import DiscoveredAsset
from app.models.assets import Asset
from app.models.lineage import LineageEdge


class LineageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _find_asset_by_name(self, org_id: uuid.UUID, name: str) -> uuid.UUID | None:
        row = (
            await self.db.execute(
                select(Asset.id).where(Asset.org_id == org_id, Asset.name == name).limit(1)
            )
        ).scalar_one_or_none()
        return row

    async def process_raw_lineage(
        self, org_id: uuid.UUID, transformation_asset_id: uuid.UUID, asset: DiscoveredAsset
    ) -> int:
        """Create edges source->target for each lineage record on the asset."""
        created = 0
        for edge in asset.raw_lineage or []:
            sources = edge.get("sources", []) or []
            targets = edge.get("targets", []) or []
            for s in sources:
                for t in targets:
                    sid = await self._find_asset_by_name(org_id, str(s).split(".")[-1])
                    tid = await self._find_asset_by_name(org_id, str(t).split(".")[-1])
                    if not sid or not tid or sid == tid:
                        continue
                    exists = (
                        await self.db.execute(
                            select(LineageEdge.id).where(
                                LineageEdge.source_asset_id == sid,
                                LineageEdge.target_asset_id == tid,
                                LineageEdge.transformation_asset_id == transformation_asset_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if exists:
                        continue
                    self.db.add(LineageEdge(
                        org_id=org_id, source_asset_id=sid, target_asset_id=tid,
                        transformation_asset_id=transformation_asset_id,
                        transformation_logic=edge.get("transformation_file"),
                    ))
                    created += 1
        await self.db.flush()
        return created

    async def graph(self, org_id: uuid.UUID) -> dict:
        edges = (
            await self.db.execute(select(LineageEdge).where(LineageEdge.org_id == org_id))
        ).scalars().all()
        node_ids = set()
        for e in edges:
            node_ids.add(e.source_asset_id)
            node_ids.add(e.target_asset_id)
        nodes = []
        if node_ids:
            assets = (
                await self.db.execute(select(Asset).where(Asset.id.in_(node_ids)))
            ).scalars().all()
            nodes = [
                {"id": str(a.id), "name": a.name, "asset_type": a.asset_type,
                 "sensitivity_level": a.sensitivity_level}
                for a in assets
            ]
        return {
            "nodes": nodes,
            "edges": [
                {"id": str(e.id), "source": str(e.source_asset_id),
                 "target": str(e.target_asset_id),
                 "transformation": e.transformation_logic}
                for e in edges
            ],
        }
