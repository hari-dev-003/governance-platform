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
from app.services.dataset_loader import load_asset_rows, numeric_series
from app.services.drift_service import detect_drift
from app.services.monitoring_service import data_drift_report

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class ConfigIn(BaseModel):
    model_version_id: uuid.UUID
    endpoint_url: str | None = None
    check_interval_minutes: int = 60
    psi_threshold: float = 0.2
    accuracy_degradation_threshold: float = 0.05
    reference_dataset_id: uuid.UUID | None = None
    current_dataset_id: uuid.UUID | None = None


class DriftCheckIn(BaseModel):
    model_version_id: uuid.UUID
    feature: str
    baseline: list[float] = []
    current: list[float] = []
    # Or sample the `feature` column from catalog table assets:
    baseline_dataset_id: uuid.UUID | None = None
    current_dataset_id: uuid.UUID | None = None
    psi_threshold: float = 0.2


class EvidentlyIn(BaseModel):
    model_version_id: uuid.UUID | None = None
    reference: list[dict] = []
    current: list[dict] = []
    reference_dataset_id: uuid.UUID | None = None
    current_dataset_id: uuid.UUID | None = None


class ConfigUpdate(BaseModel):
    endpoint_url: str | None = None
    check_interval_minutes: int | None = None
    psi_threshold: float | None = None
    accuracy_degradation_threshold: float | None = None
    is_active: bool | None = None
    reference_dataset_id: uuid.UUID | None = None
    current_dataset_id: uuid.UUID | None = None


def _config_out(c: MonitoringConfig) -> dict:
    return {"id": str(c.id), "model_version_id": str(c.model_version_id),
            "endpoint_url": c.endpoint_url, "check_interval_minutes": c.check_interval_minutes,
            "psi_threshold": c.psi_threshold,
            "accuracy_degradation_threshold": c.accuracy_degradation_threshold,
            "is_active": c.is_active,
            "reference_dataset_id": str(c.reference_dataset_id) if c.reference_dataset_id else None,
            "current_dataset_id": str(c.current_dataset_id) if c.current_dataset_id else None,
            "created_at": c.created_at.isoformat() if c.created_at else None}


@router.post("/configs", status_code=201)
async def create_config(payload: ConfigIn, db: AsyncSession = Depends(get_db),
                        user: User = Depends(ai_governance)):
    cfg = MonitoringConfig(**payload.model_dump())
    db.add(cfg)
    await db.flush()
    return _config_out(cfg)


@router.get("/configs")
async def list_configs(model_version_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    stmt = select(MonitoringConfig).order_by(MonitoringConfig.created_at.desc())
    if model_version_id:
        stmt = stmt.where(MonitoringConfig.model_version_id == model_version_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [_config_out(c) for c in rows]


@router.patch("/configs/{config_id}")
async def update_config(config_id: uuid.UUID, payload: ConfigUpdate,
                        db: AsyncSession = Depends(get_db), user: User = Depends(ai_governance)):
    cfg = await db.get(MonitoringConfig, config_id)
    if not cfg:
        raise HTTPException(404, "config not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    await db.flush()
    return _config_out(cfg)


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(config_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(ai_governance)):
    cfg = await db.get(MonitoringConfig, config_id)
    if cfg:
        await db.delete(cfg)
    return None


@router.post("/drift-check")
async def drift_check(payload: DriftCheckIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(ai_governance)):
    """Univariate drift via alibi-detect KSDrift (PSI reported alongside)."""
    baseline, current = payload.baseline, payload.current
    try:
        if not baseline and payload.baseline_dataset_id:
            baseline = numeric_series(await load_asset_rows(db, payload.baseline_dataset_id), payload.feature)
        if not current and payload.current_dataset_id:
            current = numeric_series(await load_asset_rows(db, payload.current_dataset_id), payload.feature)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"could not load dataset: {str(e)[:200]}")
    if not baseline or not current:
        raise HTTPException(400, "need baseline & current values (inline or via dataset ids)")
    verdict = detect_drift(baseline, current, psi_threshold=payload.psi_threshold)
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
    reference, current = payload.reference, payload.current
    try:
        if not reference and payload.reference_dataset_id:
            reference = await load_asset_rows(db, payload.reference_dataset_id)
        if not current and payload.current_dataset_id:
            current = await load_asset_rows(db, payload.current_dataset_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"could not load dataset: {str(e)[:200]}")
    if not reference or not current:
        raise HTTPException(400, "need reference & current datasets (inline or via dataset ids)")
    report = data_drift_report(reference, current)
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


@router.post("/run-all")
async def run_all_monitors(db: AsyncSession = Depends(get_db), user: User = Depends(ai_governance)):
    """Sweep every active monitoring config that has both datasets set, run an
    Evidently drift report, and raise alerts. Intended to be invoked on a schedule."""
    configs = (await db.execute(
        select(MonitoringConfig).where(MonitoringConfig.is_active.is_(True))
    )).scalars().all()
    checked = 0
    alerts_raised = 0
    skipped = 0
    for cfg in configs:
        if not (cfg.reference_dataset_id and cfg.current_dataset_id):
            skipped += 1
            continue
        try:
            reference = await load_asset_rows(db, cfg.reference_dataset_id)
            current = await load_asset_rows(db, cfg.current_dataset_id)
        except Exception:  # noqa: BLE001
            skipped += 1
            continue
        if not reference or not current:
            skipped += 1
            continue
        report = data_drift_report(reference, current)
        checked += 1
        if report.get("dataset_drift"):
            share = float(report.get("share_drifted") or 0)
            db.add(DriftAlert(
                model_version_id=cfg.model_version_id, monitoring_config_id=cfg.id,
                drift_type="data_drift",
                severity="critical" if share >= 0.5 else "warning",
                affected_features=[c["column"] for c in report.get("per_column", [])
                                   if c.get("drift_detected")],
                detection_metrics={"engine": "evidently",
                                   "drifted_columns": report.get("drifted_columns"),
                                   "share_drifted": share},
            ))
            alerts_raised += 1
    await db.flush()
    if alerts_raised:
        await audit.record(db, org_id=user.org_id, user_id=user.id, action="monitoring.swept",
                           resource_type="monitoring", resource_id=None,
                           new_value={"checked": checked, "alerts": alerts_raised})
    return {"active_configs": len(configs), "checked": checked,
            "alerts_raised": alerts_raised, "skipped": skipped}
