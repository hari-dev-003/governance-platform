"""Catalog service — upserts discovered assets into the unified catalog."""
from __future__ import annotations

import uuid
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import DiscoveredAsset
from app.models.assets import Asset
from app.models.sources import DataSource


class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_asset(
        self,
        source: DataSource,
        asset: DiscoveredAsset,
        ext_to_id: Dict[str, uuid.UUID],
    ) -> uuid.UUID:
        """Insert or update one asset; resolve parent via the external-id map."""
        parent_uuid = ext_to_id.get(asset.parent_id) if asset.parent_id else None

        existing = (
            await self.db.execute(
                select(Asset).where(
                    Asset.org_id == source.org_id,
                    Asset.source_id == source.id,
                    Asset.external_id == asset.external_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.name = asset.name
            existing.asset_type = asset.asset_type
            existing.parent_id = parent_uuid
            existing.technical_metadata = asset.metadata
            row = existing
        else:
            row = Asset(
                org_id=source.org_id,
                source_id=source.id,
                external_id=asset.external_id,
                name=asset.name,
                asset_type=asset.asset_type,
                parent_id=parent_uuid,
                technical_metadata=asset.metadata,
            )
            self.db.add(row)

        await self.db.flush()
        ext_to_id[asset.external_id] = row.id
        return row.id
