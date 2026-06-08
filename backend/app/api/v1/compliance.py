"""Compliance center: frameworks, requirements, mappings, status."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.compliance import (
    ComplianceFramework, ComplianceMapping, ComplianceRequirement,
)
from app.models.identity import User
from app.services import audit
from app.services.compliance_service import status_summary

router = APIRouter(prefix="/compliance", tags=["compliance"])


class MappingIn(BaseModel):
    requirement_id: uuid.UUID
    asset_id: uuid.UUID | None = None
    status: str = "in_progress"
    notes: str | None = None


@router.get("/frameworks")
async def frameworks(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    fws = (await db.execute(select(ComplianceFramework))).scalars().all()
    out = []
    for fw in fws:
        reqs = (await db.execute(
            select(ComplianceRequirement).where(ComplianceRequirement.framework_id == fw.id))).scalars().all()
        out.append({"id": str(fw.id), "name": fw.name, "version": fw.version,
                    "description": fw.description,
                    "requirements": [{"id": str(r.id), "article_reference": r.article_reference,
                                      "title": r.title, "description": r.description,
                                      "applies_to_risk_tiers": r.applies_to_risk_tiers} for r in reqs]})
    return out


@router.get("/mappings")
async def mappings(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(ComplianceMapping).where(ComplianceMapping.org_id == user.org_id))).scalars().all()
    return [{"id": str(m.id), "requirement_id": str(m.requirement_id),
             "asset_id": str(m.asset_id) if m.asset_id else None, "status": m.status,
             "notes": m.notes} for m in rows]


@router.post("/mappings", status_code=201)
async def create_mapping(payload: MappingIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(admin_or_steward)):
    m = ComplianceMapping(org_id=user.org_id, assigned_to=user.id, **payload.model_dump())
    db.add(m)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="compliance.mapped",
                       resource_type="compliance_requirement", resource_id=str(payload.requirement_id))
    return {"id": str(m.id)}


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await status_summary(db, user.org_id)
