"""Org-wide lineage graph + impact analysis."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.config import settings
from app.core.database import get_db
from app.models.identity import Organization
from app.services.openlineage_service import OpenLineageIngestor
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
async def full_graph(level: str = "table", db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return await LineageService(db).graph(user.org_id, level=level)


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


@router.post("")            # OpenLineage default endpoint -> /api/v1/lineage
@router.post("/openlineage")  # explicit alias -> /api/v1/lineage/openlineage
async def openlineage_ingest(
    payload: dict = Body(...),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Receive an OpenLineage RunEvent (Spark/Airflow/Flink/dbt/manual) and map it to lineage.

    Public endpoint for external jobs. If OPENLINEAGE_API_KEY is set, callers must send
    `Authorization: Bearer <key>` (OpenLineage HTTP transport's api_key option).
    """
    key = settings.OPENLINEAGE_API_KEY
    if key and authorization != f"Bearer {key}":
        raise HTTPException(status_code=401, detail="Invalid OpenLineage API key")
    org = (await db.execute(
        select(Organization).where(Organization.slug == settings.DEFAULT_ORG_SLUG))).scalar_one_or_none()
    if not org:
        org = (await db.execute(select(Organization))).scalars().first()
    if not org:
        raise HTTPException(status_code=400, detail="No organization configured")
    return await OpenLineageIngestor(db).ingest(org.id, payload)
