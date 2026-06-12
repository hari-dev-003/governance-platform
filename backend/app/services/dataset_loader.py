"""Load real sample rows from a catalogued dataset asset via its source connector.

Used by the AI-governance engines (bias / drift / monitoring) so they can run over
actual data referenced by a catalog asset instead of inline records pasted into the
API. Returns plain ``list[dict]`` rows (column -> value).
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector
from app.models.assets import Asset
from app.models.sources import DataSource


async def load_asset_rows(db: AsyncSession, asset_id: uuid.UUID, limit: int = 500) -> list[dict]:
    """Return up to ``limit`` sampled rows for a table (or a column's parent table)."""
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise ValueError("dataset asset not found")
    source = await db.get(DataSource, asset.source_id)
    if source is None:
        raise ValueError("dataset source not found")

    # tables sample directly; for a column asset, sample its parent table
    if asset.asset_type == "column":
        table_ext = ".".join(asset.external_id.split(".")[:-1])
    else:
        table_ext = asset.external_id

    creds = vault.decrypt(source.encrypted_credentials)
    conn = get_connector(ConnectorType(source.connector_type),
                         {**(source.connection_config or {}), **creds})
    rows = await conn.get_sample_data(table_ext, limit=limit)
    return [r for r in rows if isinstance(r, dict)]


def numeric_series(rows: list[dict], column: str) -> list[float]:
    """Extract a numeric column as floats, skipping nulls / non-numerics."""
    out: list[float] = []
    for r in rows:
        v = r.get(column)
        if v in (None, ""):
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out
