"""EU AI Act risk assessment questionnaire + scoring."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import ai_governance
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.ai_models import AIModel
from app.models.identity import User
from app.models.risk import RiskAssessment
from app.services import audit
from app.services.ai_governance_service import RISK_QUESTIONS, assess_risk

router = APIRouter(prefix="/risk-assessment", tags=["risk"])


class AssessmentIn(BaseModel):
    model_id: uuid.UUID
    responses: dict  # {question_key: bool}


@router.get("/questionnaire")
async def questionnaire(_: User = Depends(get_current_user)):
    return {"questions": RISK_QUESTIONS}


@router.post("", status_code=201)
async def submit(payload: AssessmentIn, db: AsyncSession = Depends(get_db),
                 user: User = Depends(ai_governance)):
    m = await db.get(AIModel, payload.model_id)
    if not m or m.org_id != user.org_id:
        raise HTTPException(404, "model not found")
    result = assess_risk(payload.responses)
    ra = RiskAssessment(
        model_id=payload.model_id, assessed_by=user.id,
        questionnaire_responses=payload.responses, risk_tier=result["risk_tier"],
        eu_ai_act_category=result["eu_ai_act_category"], risk_factors=result["risk_factors"],
        required_actions=result["required_actions"], status="submitted",
    )
    db.add(ra)
    m.risk_tier = result["risk_tier"]
    m.risk_assessment_status = "assessed"
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="risk.assessed",
                       resource_type="ai_model", resource_id=str(m.id), resource_name=m.name,
                       new_value={"risk_tier": result["risk_tier"]})
    return {"id": str(ra.id), **result}


@router.get("/{assessment_id}")
async def get_assessment(assessment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    ra = await db.get(RiskAssessment, assessment_id)
    if not ra:
        raise HTTPException(404, "assessment not found")
    return {"id": str(ra.id), "model_id": str(ra.model_id), "risk_tier": ra.risk_tier,
            "eu_ai_act_category": ra.eu_ai_act_category, "risk_factors": ra.risk_factors,
            "required_actions": ra.required_actions, "status": ra.status,
            "responses": ra.questionnaire_responses}


@router.post("/{assessment_id}/approve")
async def approve(assessment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  user: User = Depends(ai_governance)):
    ra = await db.get(RiskAssessment, assessment_id)
    if not ra:
        raise HTTPException(404, "assessment not found")
    ra.status = "approved"
    ra.approved_by = user.id
    await db.flush()
    return {"id": str(ra.id), "status": ra.status}


@router.get("/{assessment_id}/report")
async def report(assessment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Download the EU AI Act risk assessment as a PDF."""
    from fastapi.responses import Response
    from app.services.report_service import risk_assessment_pdf
    ra = await db.get(RiskAssessment, assessment_id)
    if not ra:
        raise HTTPException(404, "assessment not found")
    pdf = risk_assessment_pdf({
        "risk_tier": ra.risk_tier, "eu_ai_act_category": ra.eu_ai_act_category,
        "status": ra.status, "risk_factors": ra.risk_factors,
        "required_actions": ra.required_actions,
    })
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="risk-assessment-{assessment_id}.pdf"'})
