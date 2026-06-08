"""Classification rules CRUD + run classification over a source's columns."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.classification import ClassificationResult, ClassificationRule
from app.models.identity import User
from app.services import audit
from app.services.classification_service import ClassificationService

router = APIRouter(prefix="/classification", tags=["classification"])


class RuleIn(BaseModel):
    name: str
    category: str
    sensitivity_level: str
    detection_method: str  # regex | keyword
    pattern: str | None = None
    keywords: list[str] | None = None


class RuleOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    sensitivity_level: str
    detection_method: str
    pattern: str | None
    keywords: list[str] | None
    is_system_rule: bool
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(ClassificationRule).where(ClassificationRule.org_id == user.org_id)
    )).scalars().all()
    return list(rows)


@router.post("/rules", response_model=RuleOut, status_code=201)
async def create_rule(payload: RuleIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(admin_or_steward)):
    rule = ClassificationRule(org_id=user.org_id, is_system_rule=False, **payload.model_dump())
    db.add(rule)
    await db.flush()
    return rule


@router.post("/sources/{source_id}/run")
async def run_classification(source_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                             user: User = Depends(admin_or_steward)):
    result = await ClassificationService(db).classify_source_columns(user.org_id, source_id)
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="classification.run",
                       resource_type="data_source", resource_id=str(source_id))
    return result


@router.get("/results")
async def results(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(ClassificationResult).order_by(ClassificationResult.detected_at.desc()).limit(500)
    )).scalars().all()
    return [{"id": str(r.id), "asset_id": str(r.asset_id), "category": r.detected_category,
             "sensitivity": r.sensitivity_level, "confidence": r.confidence_score,
             "review_status": r.review_status,
             "detected_at": r.detected_at.isoformat() if r.detected_at else None} for r in rows]
