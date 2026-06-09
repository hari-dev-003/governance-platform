"""PostgreSQL connector - native metadata introspection + FK-based lineage (asyncpg)."""
from __future__ import annotations

from typing import Dict, List, Optional

import asyncpg

from app.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    DiscoveredAsset,
)


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

    async def _foreign_keys(self, conn) -> Dict[str, List[dict]]:
        """Map child table name -> [{parent, column}] from FK constraints (for lineage)."""
        rows = await conn.fetch(
            """
            SELECT tc.table_name AS child_table, kcu.column_name AS child_column,
                   ccu.table_name AS parent_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            """
        )
        fk: Dict[str, List[dict]] = {}
        for r in rows:
            fk.setdefault(r["child_table"], []).append(
                {"parent": r["parent_table"], "column": r["child_column"]})
        return fk

    async def discover(self) -> List[DiscoveredAsset]:
        conn = await self._connect()
        db = self.config["database"]
        assets: List[DiscoveredAsset] = []
        try:
            fk_map = await self._foreign_keys(conn)
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
                    # FK-based lineage: parent table -> this (child) table
                    raw_lineage = None
                    fks = fk_map.get(t["table_name"])
                    if fks:
                        raw_lineage = [
                            {"sources": [fk["parent"]], "targets": [t["table_name"]],
                             "transformation_file": f"FK {t['table_name']}.{fk['column']} -> {fk['parent']}"}
                            for fk in fks
                        ]
                    assets.append(DiscoveredAsset(
                        external_id=table_id, name=t["table_name"], asset_type="table",
                        parent_id=f"{db}.{schema}",
                        metadata={"table_type": t["table_type"], "row_count": t["row_count"],
                                  "last_analyzed": str(t["last_analyze"]),
                                  "foreign_keys": fks or [],
                                  "lineage_edges": raw_lineage or []},
                        raw_lineage=raw_lineage))
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
