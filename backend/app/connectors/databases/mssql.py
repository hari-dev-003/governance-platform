"""MS SQL Server connector (lazy-imports aioodbc)."""
from __future__ import annotations

from typing import List, Optional

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class MSSQLConnector(BaseConnector):
    def _dsn(self) -> str:
        c = self.config
        return (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={c['host']},{c.get('port', 1433)};"
            f"DATABASE={c['database']};UID={c['username']};PWD={c.get('password','')};"
            f"TrustServerCertificate={'yes' if c.get('trust_cert') else 'no'};"
        )

    async def test_connection(self) -> ConnectionTestResult:
        try:
            import aioodbc  # noqa
        except ImportError:
            return ConnectionTestResult(success=False, message="aioodbc not installed (pip install -r requirements-optional.txt)")
        try:
            async with await aioodbc.connect(dsn=self._dsn()) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT @@VERSION")
                    row = await cur.fetchone()
            return ConnectionTestResult(success=True, message="Connected", details={"version": row[0]})
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        import aioodbc
        db = self.config["database"]
        assets: List[DiscoveredAsset] = []
        async with await aioodbc.connect(dsn=self._dsn()) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner')"
                )
                for (schema,) in await cur.fetchall():
                    assets.append(DiscoveredAsset(external_id=f"{db}.{schema}", name=schema,
                                                  asset_type="schema", parent_id=db))
                    await cur.execute(
                        "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ?",
                        schema)
                    for (tname, ttype) in await cur.fetchall():
                        tid = f"{db}.{schema}.{tname}"
                        assets.append(DiscoveredAsset(external_id=tid, name=tname, asset_type="table",
                                                      parent_id=f"{db}.{schema}", metadata={"table_type": ttype}))
                        await cur.execute(
                            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
                            "WHERE TABLE_SCHEMA=? AND TABLE_NAME=? ORDER BY ORDINAL_POSITION", schema, tname)
                        for cn, dt, nul in await cur.fetchall():
                            assets.append(DiscoveredAsset(external_id=f"{tid}.{cn}", name=cn, asset_type="column",
                                                          parent_id=tid, metadata={"data_type": dt, "is_nullable": nul}))
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        return None
