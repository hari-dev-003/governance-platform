"""AI model registry + versions + model card."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ai_governance
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.ai_models import AIModel, AIModelVersion
from app.models.identity import User
from app.models.risk import RiskAssessment
from app.services import audit
from app.services.ai_governance_service import model_card

router = APIRouter(prefix="/ai-models", tags=["ai-models"])


class ModelIn(BaseModel):
    name: str
    description: str | None = None
    team: str | None = None
    use_case: str | None = None
    business_domain: str | None = None
    framework: str | None = None
    model_type: str | None = None


class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    risk_tier: str
    risk_assessment_status: str
    deployment_status: str
    framework: str | None
    model_type: str | None
    business_domain: str | None
    use_case: str | None
    team: str | None

    model_config = {"from_attributes": True}


class VersionIn(BaseModel):
    version_number: str
    metrics: dict = {}
    hyperparameters: dict = {}
    artifact_uri: str | None = None
    stage: str = "development"


@router.get("", response_model=list[ModelOut])
async def list_models(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(select(AIModel).where(AIModel.org_id == user.org_id))).scalars().all()
    return list(rows)


@router.post("", response_model=ModelOut, status_code=201)
async def register_model(payload: ModelIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(ai_governance)):
    m = AIModel(org_id=user.org_id, owner_id=user.id, **payload.model_dump())
    db.add(m)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="model.registered",
                       resource_type="ai_model", resource_id=str(m.id), resource_name=m.name)
    return m


@router.get("/{model_id}", response_model=ModelOut)
async def get_model(model_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    m = await db.get(AIModel, model_id)
    if not m or m.org_id != user.org_id:
        raise HTTPException(404, "model not found")
    return m


@router.patch("/{model_id}", response_model=ModelOut)
async def update_model(model_id: uuid.UUID, payload: ModelIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(ai_governance)):
    m = await db.get(AIModel, model_id)
    if not m or m.org_id != user.org_id:
        raise HTTPException(404, "model not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    await db.flush()
    return m


@router.get("/{model_id}/versions")
async def list_versions(model_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(AIModelVersion).where(AIModelVersion.model_id == model_id)
        .order_by(AIModelVersion.created_at.desc())
    )).scalars().all()
    return [{"id": str(v.id), "version_number": v.version_number, "stage": v.stage,
             "metrics": v.metrics, "validation_status": v.validation_status,
             "artifact_uri": v.artifact_uri} for v in rows]


@router.post("/{model_id}/versions", status_code=201)
async def add_version(model_id: uuid.UUID, payload: VersionIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(ai_governance)):
    m = await db.get(AIModel, model_id)
    if not m or m.org_id != user.org_id:
        raise HTTPException(404, "model not found")
    v = AIModelVersion(model_id=model_id, trained_by=user.id, **payload.model_dump())
    db.add(v)
    await db.flush()
    return {"id": str(v.id)}


@router.get("/{model_id}/card")
async def get_model_card(model_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    m = await db.get(AIModel, model_id)
    if not m or m.org_id != user.org_id:
        raise HTTPException(404, "model not found")
    versions = (await db.execute(
        select(AIModelVersion).where(AIModelVersion.model_id == model_id))).scalars().all()
    assessment = (await db.execute(
        select(RiskAssessment).where(RiskAssessment.model_id == model_id)
        .order_by(RiskAssessment.created_at.desc()).limit(1))).scalar_one_or_none()
    model_dict = {c.name: getattr(m, c.name) for c in m.__table__.columns}
    model_dict["owner"] = str(m.owner_id) if m.owner_id else None
    vlist = [{"version_number": v.version_number, "stage": v.stage, "metrics": v.metrics}
             for v in versions]
    adict = None
    if assessment:
        adict = {"risk_tier": assessment.risk_tier, "category": assessment.eu_ai_act_category,
                 "risk_factors": assessment.risk_factors, "required_actions": assessment.required_actions}
    return model_card(model_dict, vlist, adict)
