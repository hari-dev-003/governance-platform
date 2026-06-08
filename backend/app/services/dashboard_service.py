"""Dashboard aggregations across the governance domains."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_models import AIModel
from app.models.assets import Asset
from app.models.audit import AuditLog
from app.models.lineage import LineageEdge
from app.models.monitoring import DriftAlert
from app.models.sources import DataSource


async def overview(db: AsyncSession, org_id: uuid.UUID) -> dict:
    async def _count(stmt):
        return (await db.execute(stmt)).scalar() or 0

    total_assets = await _count(select(func.count()).select_from(Asset).where(Asset.org_id == org_id))
    sources = await _count(select(func.count()).select_from(DataSource).where(DataSource.org_id == org_id))
    edges = await _count(select(func.count()).select_from(LineageEdge).where(LineageEdge.org_id == org_id))
    models = await _count(select(func.count()).select_from(AIModel).where(AIModel.org_id == org_id))
    open_alerts = await _count(
        select(func.count()).select_from(DriftAlert).where(DriftAlert.status == "open"))

    sens_rows = (await db.execute(
        select(Asset.sensitivity_level, func.count())
        .where(Asset.org_id == org_id).group_by(Asset.sensitivity_level)
    )).all()
    type_rows = (await db.execute(
        select(Asset.asset_type, func.count())
        .where(Asset.org_id == org_id).group_by(Asset.asset_type)
    )).all()
    risk_rows = (await db.execute(
        select(AIModel.risk_tier, func.count())
        .where(AIModel.org_id == org_id).group_by(AIModel.risk_tier)
    )).all()
    avg_quality = (await db.execute(
        select(func.avg(Asset.quality_score)).where(Asset.org_id == org_id)
    )).scalar()

    recent = (await db.execute(
        select(AuditLog).where(AuditLog.org_id == org_id)
        .order_by(AuditLog.occurred_at.desc()).limit(10)
    )).scalars().all()

    return {
        "total_assets": total_assets,
        "data_sources": sources,
        "lineage_edges": edges,
        "ai_models": models,
        "open_drift_alerts": open_alerts,
        "avg_quality_score": round(float(avg_quality), 1) if avg_quality is not None else None,
        "sensitivity_mix": {k: v for k, v in sens_rows},
        "asset_type_mix": {k: v for k, v in type_rows},
        "risk_tier_mix": {k: v for k, v in risk_rows},
        "recent_activity": [
            {"action": a.action, "resource_type": a.resource_type,
             "resource_name": a.resource_name,
             "occurred_at": a.occurred_at.isoformat() if a.occurred_at else None}
            for a in recent
        ],
    }
