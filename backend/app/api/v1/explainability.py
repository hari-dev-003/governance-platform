"""Explainability - SHAP (global feature importance) + LIME (local explanation)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.models.identity import User
from app.services.explainability_service import (
    explain, feature_importance_from_weights, lime_available, shap_available,
)

router = APIRouter(prefix="/explainability", tags=["explainability"])


class ExplainDatasetIn(BaseModel):
    # Labelled tabular records; numeric features used to fit a surrogate model.
    records: list[dict]
    label_col: str = "label"
    instance_index: int = 0


class WeightsIn(BaseModel):
    feature_weights: dict[str, float]


@router.get("/engines")
async def engines(_: User = Depends(get_current_user)):
    return {"shap": shap_available(), "lime": lime_available()}


@router.post("/explain")
async def explain_model(payload: ExplainDatasetIn, _: User = Depends(get_current_user)):
    """SHAP global importance + LIME local explanation over a fitted sklearn model."""
    return explain(payload.records, payload.label_col, payload.instance_index)


@router.post("/feature-importance")
async def feature_importance(payload: WeightsIn, _: User = Depends(get_current_user)):
    """Lightweight weight-based attribution (no model needed)."""
    return {"engine": "weights", "features": feature_importance_from_weights(payload.feature_weights)}
