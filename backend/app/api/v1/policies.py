"""Data policies (access / retention / masking / usage purpose)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.identity import User
from app.models.policies import DataPolicy
from app.services import audit

router = APIRouter(prefix="/policies", tags=["policies"])


class PolicyIn(BaseModel):
    name: str
    policy_type: str
    rules: dict
    scope_asset_types: list[str] | None = None
    scope_sensitivity_levels: list[str] | None = None


@router.get("")
async def list_policies(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(select(DataPolicy).where(DataPolicy.org_id == user.org_id))).scalars().all()
    return [{"id": str(p.id), "name": p.name, "policy_type": p.policy_type, "rules": p.rules,
             "scope_asset_types": p.scope_asset_types,
             "scope_sensitivity_levels": p.scope_sensitivity_levels, "is_active": p.is_active}
            for p in rows]


@router.post("", status_code=201)
async def create_policy(payload: PolicyIn, db: AsyncSession = Depends(get_db),
                        user: User = Depends(admin_or_steward)):
    p = DataPolicy(org_id=user.org_id, created_by=user.id, **payload.model_dump())
    db.add(p)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="policy.created",
                       resource_type="data_policy", resource_id=str(p.id), resource_name=p.name)
    return {"id": str(p.id)}
