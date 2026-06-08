"""Access request workflow: request -> approve/reject."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.identity import User
from app.models.policies import AccessRequest
from app.services import audit

router = APIRouter(prefix="/access-requests", tags=["access"])


class RequestIn(BaseModel):
    asset_ids: list[uuid.UUID]
    access_type: str = "read"
    purpose: str
    requested_duration_days: int = 30


class ReviewIn(BaseModel):
    decision: str  # approved | rejected
    review_notes: str | None = None


@router.get("")
async def list_requests(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(AccessRequest).where(AccessRequest.org_id == user.org_id)
        .order_by(AccessRequest.requested_at.desc())
    )).scalars().all()
    return [{"id": str(r.id), "requester_id": str(r.requester_id), "access_type": r.access_type,
             "purpose": r.purpose, "status": r.status,
             "asset_ids": [str(a) for a in (r.asset_ids or [])],
             "requested_at": r.requested_at.isoformat() if r.requested_at else None} for r in rows]


@router.post("", status_code=201)
async def create_request(payload: RequestIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)):
    req = AccessRequest(org_id=user.org_id, requester_id=user.id, access_type=payload.access_type,
                        purpose=payload.purpose, requested_duration_days=payload.requested_duration_days,
                        asset_ids=payload.asset_ids)
    db.add(req)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="access.requested",
                       resource_type="access_request", resource_id=str(req.id))
    return {"id": str(req.id), "status": req.status}


@router.post("/{request_id}/review")
async def review(request_id: uuid.UUID, payload: ReviewIn, db: AsyncSession = Depends(get_db),
                 user: User = Depends(admin_or_steward)):
    req = await db.get(AccessRequest, request_id)
    if not req or req.org_id != user.org_id:
        raise HTTPException(404, "request not found")
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be approved|rejected")
    req.status = payload.decision
    req.reviewed_by = user.id
    req.review_notes = payload.review_notes
    if payload.decision == "approved":
        req.expires_at = datetime.now(timezone.utc) + timedelta(days=req.requested_duration_days)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action=f"access.{payload.decision}",
                       resource_type="access_request", resource_id=str(req.id))
    return {"id": str(req.id), "status": req.status}
