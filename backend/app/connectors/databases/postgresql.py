"""PostgreSQL connector - native metadata introspection (asyncpg). No FK lineage."""
from __future__ import annotations

from typing import Dict, List, Optional

import asyncpg

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class PostgreSQLConnector(BaseConnector):
    async def _connect(self) -> asyncpg.Connection:
        cfg = self.config
        return await asyncpg.connect(
            host=cfg["host"], port=int(cfg.get("port", 5432)), database=cfg["database"],
            user=cfg["username"], password=cfg.get("password"),
            ssl=cfg.get("ssl") or None, timeout=15)

    async def test_connection(self) -> ConnectionTestResult:
        try:
            conn = await self._connect()
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            return ConnectionTestResult(success=True, message="Connected", details={"version": version})
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        conn = await self._connect()
        db = self.config["database"]
        assets: List[DiscoveredAsset] = []
        try:
            schemas = await conn.fetch(
                """
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast')
                """)
            for s in schemas:
                schema = s["schema_name"]
                assets.append(DiscoveredAsset(
                    external_id=f"{db}.{schema}", name=schema, asset_type="schema",
                    parent_id=db, metadata={"database": db}))
                tables = await conn.fetch(
                    """
                    SELECT t.table_name, t.table_type,
                           st.n_live_tup AS row_count, st.last_analyze
                    FROM information_schema.tables t
                    LEFT JOIN pg_stat_user_tables st
                      ON st.schemaname = t.table_schema AND st.relname = t.table_name
                    WHERE t.table_schema = $1
                    """, schema)
                for t in tables:
                    table_id = f"{db}.{schema}.{t['table_name']}"
                    assets.append(DiscoveredAsset(
                        external_id=table_id, name=t["table_name"], asset_type="table",
                        parent_id=f"{db}.{schema}",
                        metadata={"table_type": t["table_type"], "row_count": t["row_count"],
                                  "last_analyzed": str(t["last_analyze"])}))
                    cols = await conn.fetch(
                        """
                        SELECT column_name, data_type, is_nullable, column_default,
                               character_maximum_length, ordinal_position
                        FROM information_schema.columns
                        WHERE table_schema = $1 AND table_name = $2
                        ORDER BY ordinal_position
                        """, schema, t["table_name"])
                    for c in cols:
                        assets.append(DiscoveredAsset(
                            external_id=f"{table_id}.{c['column_name']}", name=c["column_name"],
                            asset_type="column", parent_id=table_id,
                            metadata={"data_type": c["data_type"], "is_nullable": c["is_nullable"],
                                      "default_value": c["column_default"],
                                      "max_length": c["character_maximum_length"],
                                      "position": c["ordinal_position"]}))
        finally:
            await conn.close()
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        for a in await self.discover():
            if a.external_id == external_id:
                return a
        return None

    async def get_sample_data(self, external_id: str, limit: int = 10) -> List[Dict]:
        parts = external_id.split(".")
        if len(parts) < 3:
            return []
        schema, table = parts[1], parts[2]
        conn = await self._connect()
        try:
            rows = await conn.fetch(f'SELECT * FROM "{schema}"."{table}" LIMIT {int(limit)}')
            return [dict(r) for r in rows]
        finally:
            await conn.close()
