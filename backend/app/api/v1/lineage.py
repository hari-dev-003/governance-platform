"""Org-wide lineage graph + impact analysis."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.assets import Asset
from app.models.identity import User
from app.models.lineage import LineageEdge
from app.services.lineage_service import LineageService

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.post("/rebuild")
async def rebuild(db: AsyncSession = Depends(get_db), user: User = Depends(admin_or_steward)):
    """Re-resolve lineage from all ETL scripts + FKs against the current catalog (all connectors)."""
    from app.services import audit
    result = await LineageService(db).rebuild_org_lineage(user.org_id)
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="lineage.rebuilt",
                       resource_type="lineage", new_value=result)
    return result


@router.get("/graph")
async def full_graph(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await LineageService(db).graph(user.org_id)


@router.get("/impact/{asset_id}")
async def impact(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Downstream BFS — everything that would break if this asset changes."""
    visited: set[uuid.UUID] = set()
    frontier = [asset_id]
    while frontier:
        cur = frontier.pop()
        if cur in visited:
            continue
        visited.add(cur)
        nxt = (await db.execute(
            select(LineageEdge.target_asset_id).where(LineageEdge.source_asset_id == cur)
        )).scalars().all()
        frontier.extend(nxt)
    visited.discard(asset_id)
    assets = (await db.execute(select(Asset).where(Asset.id.in_(visited or {asset_id})))).scalars().all()
    return {"impacted_count": len(visited),
            "impacted_assets": [{"id": str(a.id), "name": a.name, "asset_type": a.asset_type}
                                for a in assets if a.id != asset_id]}
