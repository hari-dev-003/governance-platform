"""Bias & fairness testing."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ai_governance
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.bias import BiasTestRun
from app.models.identity import User
from app.services import audit
from app.services.bias_service import compute_group_metrics

router = APIRouter(prefix="/bias-tests", tags=["bias"])


class BiasTestIn(BaseModel):
    model_version_id: uuid.UUID
    protected_attribute: str
    label_column: str = "label"
    prediction_column: str = "prediction"
    positive_label: str = "1"
    # Inline evaluation records: [{protected_attribute, label, prediction}, ...]
    records: list[dict]


@router.post("", status_code=201)
async def run_bias_test(payload: BiasTestIn, db: AsyncSession = Depends(get_db),
                        user: User = Depends(ai_governance)):
    if not payload.records:
        raise HTTPException(400, "records are required for bias evaluation")
    metrics = compute_group_metrics(
        payload.records, payload.protected_attribute, payload.label_column,
        payload.prediction_column, payload.positive_label,
    )
    run = BiasTestRun(
        model_version_id=payload.model_version_id, triggered_by=user.id,
        protected_attributes=[payload.protected_attribute], label_column=payload.label_column,
        prediction_column=payload.prediction_column, positive_label=payload.positive_label,
        status="completed", overall_bias_verdict=metrics["verdict"],
        demographic_parity=metrics["demographic_parity"],
        equal_opportunity=metrics["equal_opportunity"],
        predictive_parity=metrics["predictive_parity"],
        summary_report=f"Verdict={metrics['verdict']} (DP gap {metrics['demographic_parity_gap']}, "
                       f"EO gap {metrics['equal_opportunity_gap']}, engine={metrics['engine']})",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="bias.tested",
                       resource_type="model_version", resource_id=str(payload.model_version_id),
                       new_value={"verdict": metrics["verdict"]})
    return {"id": str(run.id), **metrics}


@router.get("/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)):
    r = await db.get(BiasTestRun, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return {"id": str(r.id), "verdict": r.overall_bias_verdict, "status": r.status,
            "demographic_parity": r.demographic_parity, "equal_opportunity": r.equal_opportunity,
            "predictive_parity": r.predictive_parity, "summary": r.summary_report}


@router.get("")
async def list_runs(model_version_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    stmt = select(BiasTestRun).order_by(BiasTestRun.started_at.desc()).limit(100)
    if model_version_id:
        stmt = stmt.where(BiasTestRun.model_version_id == model_version_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": str(r.id), "verdict": r.overall_bias_verdict, "status": r.status,
             "started_at": r.started_at.isoformat() if r.started_at else None} for r in rows]
