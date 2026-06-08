"""Explainability - SHAP (global) + LIME (local)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.models.identity import User
from app.services.explainability_service import explain

router = APIRouter(prefix="/explainability", tags=["explainability"])


class ExplainDatasetIn(BaseModel):
    records: list[dict]
    label_col: str = "label"
    instance_index: int = 0


@router.post("/explain")
async def explain_model(payload: ExplainDatasetIn, _: User = Depends(get_current_user)):
    """SHAP global importance + LIME local explanation over a fitted sklearn model."""
    return explain(payload.records, payload.label_col, payload.instance_index)
