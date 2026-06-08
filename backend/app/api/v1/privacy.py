"""Data privacy / PII discovery (Microsoft Presidio)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.classification import ClassificationResult
from app.models.identity import User
from app.services import audit
from app.services.privacy_service import PrivacyService

router = APIRouter(prefix="/privacy", tags=["privacy"])


@router.post("/sources/{source_id}/scan")
async def scan(source_id: uuid.UUID, db: AsyncSession = Depends(get_db),
               user: User = Depends(admin_or_steward)):
    result = await PrivacyService(db).scan_source(user.org_id, source_id)
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="privacy.scan",
                       resource_type="data_source", resource_id=str(source_id),
                       new_value={"findings": result.get("findings"), "engine": result.get("engine")})
    return result


@router.get("/findings")
async def findings(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(ClassificationResult).order_by(ClassificationResult.detected_at.desc()).limit(500)
    )).scalars().all()
    return [{"id": str(r.id), "asset_id": str(r.asset_id), "category": r.detected_category,
             "sensitivity": r.sensitivity_level, "confidence": r.confidence_score,
             "detected_at": r.detected_at.isoformat() if r.detected_at else None} for r in rows]
