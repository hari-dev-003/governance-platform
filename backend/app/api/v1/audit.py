"""Audit log search."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditLog
from app.models.identity import User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def logs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
               action: str | None = Query(None), resource_type: str | None = Query(None),
               limit: int = Query(200, le=2000)):
    stmt = select(AuditLog).where(AuditLog.org_id == user.org_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    stmt = stmt.order_by(AuditLog.occurred_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": str(r.id), "action": r.action, "resource_type": r.resource_type,
             "resource_id": r.resource_id, "resource_name": r.resource_name,
             "new_value": r.new_value,
             "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None} for r in rows]
