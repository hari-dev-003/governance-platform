"""OpenLineage ingestion - engine-agnostic runtime lineage (Spark/Airflow/Flink/dbt/...).

Accepts standard OpenLineage RunEvents and maps their input/output datasets and
columnLineage facets onto the catalog's lineage_edges. Datasets that aren't in the
catalog become lightweight placeholder nodes so external lineage still renders.
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets import Asset
from app.models.lineage import LineageEdge
from app.services.lineage_service import _segments, build_match_index, resolve_ref


# ---------------------------------------------------------------------------
# Pure parser (no DB) — easy to unit test
# ---------------------------------------------------------------------------
def extract_lineage(payload: dict) -> dict:
    job = payload.get("job") or {}
    run = payload.get("run") or {}

    def datasets(key) -> List[dict]:
        out = []
        for d in payload.get(key) or []:
            name = d.get("name")
            if not name:
                continue
            out.append({"namespace": d.get("namespace") or "external",
                        "name": str(name), "facets": d.get("facets") or {}})
        return out

    inputs, outputs = datasets("inputs"), datasets("outputs")

    col_edges: List[dict] = []
    for o in outputs:
        fields = ((o["facets"].get("columnLineage") or {}).get("fields") or {})
        for out_field, spec in fields.items():
            for inf in (spec.get("inputFields") or []):
                if inf.get("name") and inf.get("field"):
                    col_edges.append({
                        "output_dataset": o["name"], "output_field": out_field,
                        "input_dataset": str(inf["name"]), "input_field": str(inf["field"])})

    return {
        "job_namespace": job.get("namespace") or "default",
        "job_name": job.get("name") or "unknown_job",
        "run_id": run.get("runId"),
        "event_type": payload.get("eventType"),
        "inputs": inputs, "outputs": outputs, "column_edges": col_edges,
    }


# ---------------------------------------------------------------------------
# DB ingestion
# ---------------------------------------------------------------------------
class OpenLineageIngestor:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _index_add(index: dict, aid: uuid.UUID, name: str, ext: str) -> None:
        if ext:
            index["exact"][ext.strip().lower()] = aid
            segs = _segments(ext)
            for k in range(1, min(3, len(segs)) + 1):
                index["qualified"].setdefault(".".join(segs[-k:]), set()).add(aid)
        if name:
            index["by_name"].setdefault(name.strip().lower(), set()).add(aid)

    async def _get_or_create(self, org_id, external_id, name, asset_type,
                             parent_id=None, metadata=None) -> uuid.UUID:
        existing = (await self.db.execute(
            select(Asset).where(Asset.org_id == org_id, Asset.external_id == external_id,
                                Asset.source_id.is_(None)))).scalar_one_or_none()
        if existing:
            return existing.id
        row = Asset(org_id=org_id, source_id=None, external_id=external_id, name=name,
                    asset_type=asset_type, parent_id=parent_id,
                    technical_metadata=metadata or {})
        self.db.add(row)
        await self.db.flush()
        return row.id

    async def _resolve_or_create_dataset(self, org_id, index, ds: dict) -> uuid.UUID:
        r = resolve_ref(ds["name"], index)
        if r:
            return r[0]
        ext = f"{ds['namespace']}:{ds['name']}"
        name = ds["name"].split(".")[-1] or ds["name"]
        aid = await self._get_or_create(org_id, ext, name, "dataset",
                                        metadata={"source": "openlineage", "namespace": ds["namespace"]})
        self._index_add(index, aid, name, ext)
        # also index by the OL name so column refs ("dataset.field") resolve
        self._index_add(index, aid, ds["name"], ds["name"])
        return aid

    async def _resolve_or_create_column(self, org_id, index, dataset_name, field) -> uuid.UUID:
        ref = f"{dataset_name}.{field}"
        r = resolve_ref(ref, index)
        if r:
            return r[0]
        parent = await self._resolve_or_create_dataset(
            org_id, index, {"namespace": "external", "name": dataset_name})
        # parent external_id may be a real catalog one or placeholder; derive column ext from it
        prow = await self.db.get(Asset, parent)
        col_ext = f"{prow.external_id}.{field}"
        aid = await self._get_or_create(org_id, col_ext, field, "column", parent_id=parent,
                                        metadata={"source": "openlineage"})
        self._index_add(index, aid, field, col_ext)
        self._index_add(index, aid, field, f"{dataset_name}.{field}")
        return aid

    async def _add_edge(self, org_id, sid, tid, transform_id, ltype, logic) -> int:
        if sid == tid:
            return 0
        exists = (await self.db.execute(select(LineageEdge.id).where(
            LineageEdge.source_asset_id == sid, LineageEdge.target_asset_id == tid,
            LineageEdge.transformation_asset_id == transform_id,
            LineageEdge.lineage_type == ltype))).scalar_one_or_none()
        if exists:
            return 0
        self.db.add(LineageEdge(org_id=org_id, source_asset_id=sid, target_asset_id=tid,
                                transformation_asset_id=transform_id, lineage_type=ltype,
                                transformation_logic=logic, confidence_score=1.0))
        return 1

    async def ingest(self, org_id: uuid.UUID, payload: dict) -> dict:
        info = extract_lineage(payload)
        if not info["inputs"] and not info["outputs"]:
            return {"status": "ignored", "reason": "event has no input/output datasets"}

        # job node (the transformation)
        job_ext = f"openlineage://{info['job_namespace']}/{info['job_name']}"
        job_id = await self._get_or_create(
            org_id, job_ext, info["job_name"], "etl_pipeline",
            metadata={"engine": "openlineage", "namespace": info["job_namespace"],
                      "run_id": info["run_id"], "event_type": info["event_type"]})

        # index over current catalog
        rows = (await self.db.execute(
            select(Asset.id, Asset.name, Asset.external_id).where(Asset.org_id == org_id))).all()
        index = build_match_index((r[0], r[1], r[2]) for r in rows)

        in_ids = [await self._resolve_or_create_dataset(org_id, index, d) for d in info["inputs"]]
        out_ids = [await self._resolve_or_create_dataset(org_id, index, d) for d in info["outputs"]]

        table_edges = 0
        for s in in_ids:
            for t in out_ids:
                table_edges += await self._add_edge(org_id, s, t, job_id, "table", info["job_name"])

        col_edges = 0
        for ce in info["column_edges"]:
            s = await self._resolve_or_create_column(org_id, index, ce["input_dataset"], ce["input_field"])
            t = await self._resolve_or_create_column(org_id, index, ce["output_dataset"], ce["output_field"])
            col_edges += await self._add_edge(org_id, s, t, job_id, "column", info["job_name"])

        await self.db.flush()
        return {"status": "ok", "job": info["job_name"], "inputs": len(in_ids),
                "outputs": len(out_ids), "table_edges_created": table_edges,
                "column_edges_created": col_edges}
