"""Asset catalog: search, detail, update governance metadata, columns, lineage."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.assets import Asset
from app.models.lineage import LineageEdge
from app.models.identity import User
from app.services import audit

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetOut(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    sensitivity_level: str
    domain: str | None
    business_description: str | None
    tags: list[str]
    quality_score: float | None
    parent_id: uuid.UUID | None
    source_id: uuid.UUID | None
    technical_metadata: dict

    model_config = {"from_attributes": True}


class AssetUpdate(BaseModel):
    business_description: Optional[str] = None
    domain: Optional[str] = None
    sensitivity_level: Optional[str] = None
    tags: Optional[list[str]] = None
    owner_id: Optional[uuid.UUID] = None
    steward_id: Optional[uuid.UUID] = None
    is_deprecated: Optional[bool] = None


@router.get("")
async def search_assets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    q: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    sensitivity: Optional[str] = Query(None),
    source_id: Optional[uuid.UUID] = Query(None),
    domain: Optional[str] = Query(None),
    has_pii: Optional[bool] = Query(None),
    sort: str = Query("recent"),       # recent | name | quality
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    from sqlalchemy import func
    conds = [Asset.org_id == user.org_id]
    if q:
        conds.append(or_(Asset.name.ilike(f"%{q}%"), Asset.external_id.ilike(f"%{q}%")))
    if type:
        conds.append(Asset.asset_type == type)
    if sensitivity:
        conds.append(Asset.sensitivity_level == sensitivity)
    if source_id:
        conds.append(Asset.source_id == source_id)
    if domain:
        conds.append(Asset.domain == domain)
    if has_pii:
        conds.append(Asset.sensitivity_level.in_(("confidential", "restricted")))

    total = (await db.execute(select(func.count()).select_from(Asset).where(*conds))).scalar() or 0
    stmt = select(Asset).where(*conds)
    if sort == "name":
        stmt = stmt.order_by(Asset.name.asc())
    elif sort == "quality":
        stmt = stmt.order_by(Asset.quality_score.desc().nullslast())
    else:
        stmt = stmt.order_by(Asset.first_seen_at.desc())
    rows = (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    items = [AssetOut.model_validate(a).model_dump() for a in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    a = await db.get(Asset, asset_id)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "asset not found")
    return a


@router.get("/{asset_id}/columns", response_model=list[AssetOut])
async def get_columns(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(Asset).where(Asset.parent_id == asset_id, Asset.org_id == user.org_id)
    )).scalars().all()
    return list(rows)


@router.get("/{asset_id}/lineage")
async def asset_lineage(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    up = (await db.execute(select(LineageEdge).where(LineageEdge.target_asset_id == asset_id))).scalars().all()
    down = (await db.execute(select(LineageEdge).where(LineageEdge.source_asset_id == asset_id))).scalars().all()
    ids = {asset_id}
    for e in up:
        ids.add(e.source_asset_id)
    for e in down:
        ids.add(e.target_asset_id)
    assets = (await db.execute(select(Asset).where(Asset.id.in_(ids)))).scalars().all()
    nodes = [{"id": str(a.id), "name": a.name, "asset_type": a.asset_type,
              "sensitivity_level": a.sensitivity_level, "is_center": a.id == asset_id}
             for a in assets]
    edges = [{"id": str(e.id), "source": str(e.source_asset_id), "target": str(e.target_asset_id)}
             for e in (list(up) + list(down))]
    return {"nodes": nodes, "edges": edges}


@router.get("/{asset_id}/classifications")
async def asset_classifications(asset_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                                user: User = Depends(get_current_user)):
    """PII/classification findings for this asset and its columns."""
    from app.models.classification import ClassificationResult
    child_ids = (await db.execute(select(Asset.id).where(Asset.parent_id == asset_id))).scalars().all()
    ids = [asset_id, *child_ids]
    rows = (await db.execute(
        select(ClassificationResult, Asset.name)
        .join(Asset, Asset.id == ClassificationResult.asset_id)
        .where(ClassificationResult.asset_id.in_(ids))
        .order_by(ClassificationResult.detected_at.desc()))).all()
    return [{"column": name, "category": r.detected_category, "sensitivity": r.sensitivity_level,
             "confidence": r.confidence_score} for r, name in rows]


@router.get("/{asset_id}/sample")
async def asset_sample(asset_id: uuid.UUID, limit: int = Query(20, le=100),
                       db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """Preview sample rows for a table/view via its connector."""
    from app.connectors.base import ConnectorType
    from app.connectors.credential_vault import vault
    from app.connectors.registry import get_connector
    from app.models.sources import DataSource
    a = await db.get(Asset, asset_id)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "asset not found")
    src = await db.get(DataSource, a.source_id)
    if not src:
        return {"columns": [], "rows": []}
    try:
        conn = get_connector(ConnectorType(src.connector_type),
                             {**(src.connection_config or {}), **vault.decrypt(src.encrypted_credentials)})
        rows = await conn.get_sample_data(a.external_id, limit=limit)
    except Exception as e:  # noqa: BLE001
        return {"columns": [], "rows": [], "error": str(e)[:200]}
    cols = list(rows[0].keys()) if rows else []
    return {"columns": cols, "rows": [[str(r.get(c)) for c in cols] for r in rows]}


@router.patch("/{asset_id}", response_model=AssetOut)
async def update_asset(asset_id: uuid.UUID, payload: AssetUpdate, db: AsyncSession = Depends(get_db),
                       user: User = Depends(admin_or_steward)):
    a = await db.get(Asset, asset_id)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "asset not found")
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(a, k, v)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="asset.updated",
                       resource_type="asset", resource_id=str(asset_id), resource_name=a.name,
                       new_value={k: str(v) for k, v in changes.items()})
    return a
