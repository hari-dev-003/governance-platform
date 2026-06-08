"""Amazon Redshift connector — speaks the Postgres wire protocol (asyncpg)."""
from __future__ import annotations

from typing import List, Optional

import asyncpg

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class RedshiftConnector(BaseConnector):
    async def _connect(self) -> asyncpg.Connection:
        c = self.config
        return await asyncpg.connect(
            host=c["host"], port=int(c.get("port", 5439)), database=c["database"],
            user=c["username"], password=c.get("password"), timeout=20,
        )

    async def test_connection(self) -> ConnectionTestResult:
        try:
            conn = await self._connect()
            v = await conn.fetchval("SELECT version()")
            await conn.close()
            return ConnectionTestResult(success=True, message="Connected to Redshift", details={"version": v})
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        conn = await self._connect()
        db = self.config["database"]
        assets: List[DiscoveredAsset] = []
        try:
            rows = await conn.fetch(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema')")
            for r in rows:
                schema, table = r["table_schema"], r["table_name"]
                tid = f"{db}.{schema}.{table}"
                assets.append(DiscoveredAsset(external_id=tid, name=table, asset_type="table",
                                              parent_id=f"{db}.{schema}", metadata={"schema": schema}))
        finally:
            await conn.close()
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
