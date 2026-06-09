"""Catalog landing — overview dashboard + facets for filtering."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.identity import User
from app.services.catalog_overview import facets, overview

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/overview")
async def catalog_overview(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await overview(db, user.org_id)


@router.get("/facets")
async def catalog_facets(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await facets(db, user.org_id)
