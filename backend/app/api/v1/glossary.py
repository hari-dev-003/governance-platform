"""Business glossary with a draft -> pending -> approved workflow."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.glossary import GlossaryTerm, TermAssetLink
from app.models.identity import User
from app.services import audit

router = APIRouter(prefix="/glossary", tags=["glossary"])


class TermIn(BaseModel):
    name: str
    definition: str
    domain: str | None = None
    synonyms: list[str] = []
    examples: str | None = None


class TermOut(BaseModel):
    id: uuid.UUID
    name: str
    definition: str
    domain: str | None
    status: str
    synonyms: list[str]
    examples: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[TermOut])
async def list_terms(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(GlossaryTerm).where(GlossaryTerm.org_id == user.org_id).order_by(GlossaryTerm.name)
    )).scalars().all()
    return list(rows)


@router.post("", response_model=TermOut, status_code=201)
async def create_term(payload: TermIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(admin_or_steward)):
    exists = (await db.execute(select(GlossaryTerm).where(
        GlossaryTerm.org_id == user.org_id, GlossaryTerm.name == payload.name))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "term already exists")
    term = GlossaryTerm(org_id=user.org_id, created_by=user.id, steward_id=user.id,
                        **payload.model_dump())
    db.add(term)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="glossary.created",
                       resource_type="glossary_term", resource_id=str(term.id), resource_name=term.name)
    return term


@router.post("/{term_id}/submit", response_model=TermOut)
async def submit(term_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                 user: User = Depends(admin_or_steward)):
    term = await db.get(GlossaryTerm, term_id)
    if not term or term.org_id != user.org_id:
        raise HTTPException(404, "term not found")
    term.status = "pending_approval"
    await db.flush()
    return term


@router.post("/{term_id}/approve", response_model=TermOut)
async def approve(term_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  user: User = Depends(admin_or_steward)):
    term = await db.get(GlossaryTerm, term_id)
    if not term or term.org_id != user.org_id:
        raise HTTPException(404, "term not found")
    term.status = "approved"
    term.approved_by = user.id
    term.approved_at = datetime.now(timezone.utc)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="glossary.approved",
                       resource_type="glossary_term", resource_id=str(term.id), resource_name=term.name)
    return term


@router.post("/{term_id}/link/{asset_id}", status_code=201)
async def link_asset(term_id: uuid.UUID, asset_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     user: User = Depends(admin_or_steward)):
    exists = (await db.execute(select(TermAssetLink).where(
        TermAssetLink.term_id == term_id, TermAssetLink.asset_id == asset_id))).scalar_one_or_none()
    if not exists:
        db.add(TermAssetLink(term_id=term_id, asset_id=asset_id, linked_by=user.id))
        await db.flush()
    return {"ok": True}
