"""Catalog dashboard aggregations + facets (production-grade catalog landing)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets import Asset
from app.models.classification import ClassificationResult
from app.models.sources import DataSource

_PII_SENS = ("confidential", "restricted")


async def overview(db: AsyncSession, org_id: uuid.UUID) -> dict:
    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    base = select(func.count()).select_from(Asset).where(Asset.org_id == org_id)
    total = await scalar(base)

    type_rows = (await db.execute(
        select(Asset.asset_type, func.count()).where(Asset.org_id == org_id)
        .group_by(Asset.asset_type))).all()
    by_type = {k: v for k, v in type_rows}

    src_rows = (await db.execute(
        select(DataSource.name, func.count(Asset.id))
        .join(Asset, Asset.source_id == DataSource.id)
        .where(Asset.org_id == org_id).group_by(DataSource.name)
        .order_by(func.count(Asset.id).desc()))).all()
    by_source = [{"source": n, "count": c} for n, c in src_rows]

    sens_rows = (await db.execute(
        select(Asset.sensitivity_level, func.count()).where(Asset.org_id == org_id)
        .group_by(Asset.sensitivity_level))).all()
    by_sensitivity = {k: v for k, v in sens_rows}

    domain_rows = (await db.execute(
        select(Asset.domain, func.count()).where(Asset.org_id == org_id, Asset.domain.isnot(None))
        .group_by(Asset.domain).order_by(func.count().desc()).limit(8))).all()
    by_domain = [{"domain": d, "count": c} for d, c in domain_rows]

    # quality buckets (only assets that have been scored)
    scores = [s for (s,) in (await db.execute(
        select(Asset.quality_score).where(Asset.org_id == org_id, Asset.quality_score.isnot(None)))).all()]
    buckets = {"90-100": 0, "70-89": 0, "50-69": 0, "<50": 0}
    for s in scores:
        if s >= 90: buckets["90-100"] += 1
        elif s >= 70: buckets["70-89"] += 1
        elif s >= 50: buckets["50-69"] += 1
        else: buckets["<50"] += 1
    avg_quality = round(sum(scores) / len(scores), 1) if scores else None

    pii_columns = await scalar(
        select(func.count()).select_from(Asset).where(
            Asset.org_id == org_id, Asset.asset_type == "column",
            Asset.sensitivity_level.in_(_PII_SENS)))

    # approximate governed rows (sum of table row counts from technical_metadata)
    tbl_meta = (await db.execute(
        select(Asset.technical_metadata).where(Asset.org_id == org_id, Asset.asset_type == "table"))).all()
    total_rows = 0
    for (md,) in tbl_meta:
        try:
            total_rows += int((md or {}).get("row_count") or 0)
        except (TypeError, ValueError):
            pass

    recent = (await db.execute(
        select(Asset).where(Asset.org_id == org_id, Asset.asset_type.in_(("table", "ml_model", "etl_pipeline")))
        .order_by(Asset.first_seen_at.desc()).limit(8))).scalars().all()

    return {
        "total_assets": total,
        "counts": {"sources": len(by_source), "schemas": by_type.get("schema", 0),
                   "tables": by_type.get("table", 0), "columns": by_type.get("column", 0),
                   "ml_models": by_type.get("ml_model", 0), "pipelines": by_type.get("etl_pipeline", 0)},
        "by_type": by_type, "by_source": by_source, "by_sensitivity": by_sensitivity,
        "by_domain": by_domain, "quality_buckets": buckets, "avg_quality": avg_quality,
        "pii_columns": pii_columns, "total_rows": total_rows, "documented_pct": None,
        "recently_added": [
            {"id": str(a.id), "name": a.name, "asset_type": a.asset_type,
             "sensitivity_level": a.sensitivity_level,
             "first_seen_at": a.first_seen_at.isoformat() if a.first_seen_at else None}
            for a in recent],
    }


async def facets(db: AsyncSession, org_id: uuid.UUID) -> dict:
    src = (await db.execute(
        select(DataSource.id, DataSource.name, func.count(Asset.id))
        .join(Asset, Asset.source_id == DataSource.id)
        .where(Asset.org_id == org_id).group_by(DataSource.id, DataSource.name))).all()
    types = (await db.execute(
        select(Asset.asset_type, func.count()).where(Asset.org_id == org_id).group_by(Asset.asset_type))).all()
    sens = (await db.execute(
        select(Asset.sensitivity_level, func.count()).where(Asset.org_id == org_id)
        .group_by(Asset.sensitivity_level))).all()
    domains = (await db.execute(
        select(Asset.domain, func.count()).where(Asset.org_id == org_id, Asset.domain.isnot(None))
        .group_by(Asset.domain))).all()
    return {
        "sources": [{"id": str(i), "name": n, "count": c} for i, n, c in src],
        "asset_types": [{"value": t, "count": c} for t, c in types],
        "sensitivities": [{"value": s, "count": c} for s, c in sens],
        "domains": [{"value": d, "count": c} for d, c in domains],
    }
