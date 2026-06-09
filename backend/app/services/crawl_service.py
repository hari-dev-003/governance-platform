"""Crawl orchestration — runs a connector, upserts assets, builds lineage."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector
from app.models.sources import DataSource
from app.services.catalog_service import CatalogService
from app.services.lineage_service import LineageService


async def crawl_source(db: AsyncSession, source_id: uuid.UUID) -> dict:
    source = await db.get(DataSource, source_id)
    if not source or not source.is_active:
        return {"error": "source not found or inactive"}

    creds = vault.decrypt(source.encrypted_credentials)
    full_config = {**(source.connection_config or {}), **creds}
    connector = get_connector(ConnectorType(source.connector_type), full_config)

    discovered = await connector.discover()

    catalog = CatalogService(db)
    lineage = LineageService(db)
    ext_to_id: dict[str, uuid.UUID] = {}

    # Pass 1: upsert all assets (parents resolved as we go)
    for asset in discovered:
        await catalog.upsert_asset(source, asset, ext_to_id)

    # Pass 2: resolve lineage across the WHOLE catalog (all connectors), using
    # the qualified-name index. Works regardless of crawl order.
    rebuild = await lineage.rebuild_org_lineage(source.org_id)
    edges = rebuild["edges_created"]

    from datetime import datetime, timezone
    source.last_crawled_at = datetime.now(timezone.utc)
    source.status = "connected"
    await db.flush()

    return {"source_id": str(source.id), "assets_discovered": len(discovered),
            "lineage_edges_created": edges}
