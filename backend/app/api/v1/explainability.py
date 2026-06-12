"""Explainability - SHAP (global) + LIME (local), with persisted feature importance."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ai_governance
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.ai_models import AIModelVersion
from app.models.identity import User
from app.services.dataset_loader import load_asset_rows
from app.services.explainability_service import explain

router = APIRouter(prefix="/explainability", tags=["explainability"])


class ExplainDatasetIn(BaseModel):
    records: list[dict] = []
    dataset_id: uuid.UUID | None = None
    label_col: str = "label"
    instance_index: int = 0


async def _resolve_records(db: AsyncSession, payload: "ExplainDatasetIn") -> list[dict]:
    records = payload.records
    if not records and payload.dataset_id:
        try:
            records = await load_asset_rows(db, payload.dataset_id)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"could not load dataset: {str(e)[:200]}")
    if not records:
        raise HTTPException(400, "provide records or a dataset_id")
    return records


@router.post("/explain")
async def explain_model(payload: ExplainDatasetIn, db: AsyncSession = Depends(get_db),
                        _: User = Depends(get_current_user)):
    """SHAP global importance + LIME local explanation over a fitted sklearn model."""
    records = await _resolve_records(db, payload)
    return explain(records, payload.label_col, payload.instance_index)


@router.post("/versions/{version_id}/feature-importance")
async def compute_and_store(version_id: uuid.UUID, payload: ExplainDatasetIn,
                            db: AsyncSession = Depends(get_db), user: User = Depends(ai_governance)):
    """Compute SHAP global importance for a version's dataset and persist it."""
    v = await db.get(AIModelVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    records = await _resolve_records(db, payload)
    result = explain(records, payload.label_col, payload.instance_index)
    v.feature_importance = {
        "engine": result["engine"],
        "global_importance": result["global_importance"],
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": str(payload.dataset_id) if payload.dataset_id else None,
    }
    await db.flush()
    return {"version_id": str(version_id), **result}


@router.get("/feature-importance/{version_id}")
async def get_feature_importance(version_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                                 _: User = Depends(get_current_user)):
    """Return the last persisted global feature importance for a model version."""
    v = await db.get(AIModelVersion, version_id)
    if not v:
        raise HTTPException(404, "version not found")
    return {"version_id": str(version_id), "feature_importance": v.feature_importance}
