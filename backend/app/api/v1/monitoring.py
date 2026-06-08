"""Model monitoring - Evidently AI reports + alibi-detect drift + drift alerts."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ai_governance
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.identity import User
from app.models.monitoring import DriftAlert, MonitoringConfig
from app.services import audit
from app.services.drift_service import detect_drift
from app.services.monitoring_service import data_drift_report

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class ConfigIn(BaseModel):
    model_version_id: uuid.UUID
    endpoint_url: str | None = None
    check_interval_minutes: int = 60
    psi_threshold: float = 0.2


class DriftCheckIn(BaseModel):
    model_version_id: uuid.UUID
    feature: str
    baseline: list[float]
    current: list[float]
    psi_threshold: float = 0.2


class EvidentlyIn(BaseModel):
    model_version_id: uuid.UUID | None = None
    reference: list[dict]
    current: list[dict]


@router.post("/configs", status_code=201)
async def create_config(payload: ConfigIn, db: AsyncSession = Depends(get_db),
                        user: User = Depends(ai_governance)):
    cfg = MonitoringConfig(**payload.model_dump())
    db.add(cfg)
    await db.flush()
    return {"id": str(cfg.id)}


@router.post("/drift-check")
async def drift_check(payload: DriftCheckIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(ai_governance)):
    """Univariate drift via alibi-detect KSDrift (PSI reported alongside)."""
    verdict = detect_drift(payload.baseline, payload.current, psi_threshold=payload.psi_threshold)
    if verdict["drift"]:
        db.add(DriftAlert(
            model_version_id=payload.model_version_id, drift_type="data_drift",
            severity=verdict["severity"], affected_features=[payload.feature],
            detection_metrics={**verdict, "feature": payload.feature},
        ))
        await db.flush()
        await audit.record(db, org_id=user.org_id, user_id=user.id, action="drift.detected",
                           resource_type="model_version", resource_id=str(payload.model_version_id),
                           new_value={"engine": verdict["engine"], "severity": verdict["severity"]})
    return {"feature": payload.feature, **verdict}


@router.post("/evidently-report")
async def evidently_report(payload: EvidentlyIn, db: AsyncSession = Depends(get_db),
                           user: User = Depends(ai_governance)):
    """Full dataset drift report via Evidently AI (reference vs current)."""
    report = data_drift_report(payload.reference, payload.current)
    if payload.model_version_id and report.get("dataset_drift"):
        db.add(DriftAlert(
            model_version_id=payload.model_version_id, drift_type="data_drift",
            severity="warning", affected_features=[c["column"] for c in report.get("per_column", [])
                                                   if c.get("drift_detected")],
            detection_metrics={"engine": "evidently",
                               "drifted_columns": report.get("drifted_columns"),
                               "share_drifted": report.get("share_drifted")},
        ))
        await db.flush()
    return report


@router.get("/alerts")
async def list_alerts(status: str | None = None, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    stmt = select(DriftAlert).order_by(DriftAlert.detected_at.desc()).limit(200)
    if status:
        stmt = stmt.where(DriftAlert.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": str(a.id), "model_version_id": str(a.model_version_id), "drift_type": a.drift_type,
             "severity": a.severity, "affected_features": a.affected_features,
             "detection_metrics": a.detection_metrics, "status": a.status,
             "detected_at": a.detected_at.isoformat() if a.detected_at else None} for a in rows]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(ai_governance)):
    a = await db.get(DriftAlert, alert_id)
    if not a:
        raise HTTPException(404, "alert not found")
    a.status = "acknowledged"
    a.acknowledged_by = user.id
    await db.flush()
    return {"id": str(a.id), "status": a.status}
