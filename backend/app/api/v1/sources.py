"""Data source connections: CRUD, connectivity test, and crawl trigger."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import admin_or_steward
from app.connectors.base import CONNECTOR_CATEGORY, ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector, list_connector_types
from app.core.database import AsyncSessionLocal, get_db
from app.core.security import get_current_user
from app.models.identity import User
from app.models.sources import DataSource
from app.services import audit
from app.services.crawl_service import crawl_source
from app.services.source_service import delete_source_cascade

router = APIRouter(prefix="/sources", tags=["sources"])

# Per-connector credential vs. non-secret config split
_SECRET_KEYS = {"password", "aws_secret_access_key", "aws_access_key_id", "service_account_json",
                "connection_string", "client_secret", "github_token", "admin_password", "auth_token"}


class SourceIn(BaseModel):
    name: str
    connector_type: str
    config: dict[str, Any] = {}


class SourceOut(BaseModel):
    id: uuid.UUID
    name: str
    connector_type: str
    category: str
    is_active: bool
    status: str
    last_crawled_at: str | None = None

    model_config = {"from_attributes": True}


def _split_config(cfg: dict) -> tuple[dict, dict]:
    secrets = {k: v for k, v in cfg.items() if k in _SECRET_KEYS}
    nonsecret = {k: v for k, v in cfg.items() if k not in _SECRET_KEYS}
    return secrets, nonsecret


@router.get("/types")
async def connector_types(_: User = Depends(get_current_user)):
    return [
        {"connector_type": t, "category": CONNECTOR_CATEGORY.get(ConnectorType(t), "other")}
        for t in list_connector_types()
    ]


@router.get("", response_model=list[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(DataSource).where(DataSource.org_id == user.org_id).order_by(DataSource.created_at.desc())
    )).scalars().all()
    out = []
    for s in rows:
        out.append(SourceOut(
            id=s.id, name=s.name, connector_type=s.connector_type, category=s.category,
            is_active=s.is_active, status=s.status,
            last_crawled_at=s.last_crawled_at.isoformat() if s.last_crawled_at else None,
        ))
    return out


@router.post("", response_model=SourceOut, status_code=201)
async def create_source(payload: SourceIn, db: AsyncSession = Depends(get_db),
                        user: User = Depends(admin_or_steward)):
    try:
        ct = ConnectorType(payload.connector_type)
    except ValueError:
        raise HTTPException(400, f"unknown connector_type: {payload.connector_type}")
    secrets, nonsecret = _split_config(payload.config)
    src = DataSource(
        org_id=user.org_id, name=payload.name, connector_type=ct.value,
        category=CONNECTOR_CATEGORY[ct], encrypted_credentials=vault.encrypt(secrets),
        connection_config=nonsecret, created_by=user.id,
    )
    db.add(src)
    await db.flush()
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="source.created",
                       resource_type="data_source", resource_id=str(src.id), resource_name=src.name)
    return SourceOut.model_validate(src)


@router.post("/{source_id}/test")
async def test_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(admin_or_steward)):
    src = await db.get(DataSource, source_id)
    if not src or src.org_id != user.org_id:
        raise HTTPException(404, "source not found")
    creds = vault.decrypt(src.encrypted_credentials)
    connector = get_connector(ConnectorType(src.connector_type),
                              {**(src.connection_config or {}), **creds})
    result = await connector.test_connection()
    src.status = "connected" if result.success else "error"
    await db.flush()
    return result.model_dump()


@router.post("/{source_id}/crawl")
async def crawl_now(source_id: uuid.UUID, background: BackgroundTasks,
                    db: AsyncSession = Depends(get_db), user: User = Depends(admin_or_steward)):
    src = await db.get(DataSource, source_id)
    if not src or src.org_id != user.org_id:
        raise HTTPException(404, "source not found")
    await audit.record(db, org_id=user.org_id, user_id=user.id, action="source.crawl_triggered",
                       resource_type="data_source", resource_id=str(src.id), resource_name=src.name)

    # Run the crawl in the background using its own session (works without Celery/Redis).
    async def _bg(sid: uuid.UUID):
        async with AsyncSessionLocal() as s:
            try:
                await crawl_source(s, sid)
                await s.commit()
            except Exception:  # noqa: BLE001
                await s.rollback()

    background.add_task(_bg, source_id)
    return {"status": "queued", "source_id": str(source_id),
            "message": "Crawl started in background. Refresh the catalog shortly."}


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(admin_or_steward)):
    src = await db.get(DataSource, source_id)
    if not src or src.org_id != user.org_id:
        raise HTTPException(404, "source not found")
    source_name = src.name
    removed = await delete_source_cascade(db, src)
    await audit.record(
        db,
        org_id=user.org_id,
        user_id=user.id,
        action="source.deleted",
        resource_type="data_source",
        resource_id=str(source_id),
        resource_name=source_name,
        new_value=removed,
    )
    return None
