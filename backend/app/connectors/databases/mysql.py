"""MySQL connector - native metadata introspection via aiomysql."""
from __future__ import annotations

from typing import Dict, List, Optional

import aiomysql

from app.connectors.base import BaseConnector, ConnectionTestResult, DiscoveredAsset


class MySQLConnector(BaseConnector):
    async def _connect(self):
        cfg = self.config
        return await aiomysql.connect(
            host=cfg["host"], port=int(cfg.get("port", 3306)),
            user=cfg["username"], password=cfg.get("password", ""),
            db=cfg["database"], connect_timeout=15,
        )

    async def test_connection(self) -> ConnectionTestResult:
        try:
            conn = await self._connect()
            async with conn.cursor() as cur:
                await cur.execute("SELECT VERSION()")
                row = await cur.fetchone()
            conn.close()
            return ConnectionTestResult(success=True, message="Connected", details={"version": row[0]})
        except Exception as e:  # noqa: BLE001
            return ConnectionTestResult(success=False, message=str(e))

    async def discover(self) -> List[DiscoveredAsset]:
        db = self.config["database"]
        assets: List[DiscoveredAsset] = []
        conn = await self._connect()
        try:
            async with conn.cursor() as cur:
                # schema node = the database itself
                assets.append(DiscoveredAsset(external_id=f"{db}", name=db, asset_type="schema",
                                              parent_id=None, metadata={"database": db}))
                await cur.execute(
                    "SELECT table_name, table_type, table_rows FROM information_schema.tables "
                    "WHERE table_schema=%s", (db,))
                for tname, ttype, trows in await cur.fetchall():
                    tid = f"{db}.{tname}"
                    assets.append(DiscoveredAsset(external_id=tid, name=tname, asset_type="table",
                                                  parent_id=db,
                                                  metadata={"table_type": ttype, "row_count": trows}))
                    await cur.execute(
                        "SELECT column_name, data_type, is_nullable, column_default, ordinal_position "
                        "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s "
                        "ORDER BY ordinal_position", (db, tname))
                    for cn, dt, nul, dflt, pos in await cur.fetchall():
                        assets.append(DiscoveredAsset(
                            external_id=f"{tid}.{cn}", name=cn, asset_type="column", parent_id=tid,
                            metadata={"data_type": dt, "is_nullable": nul, "default_value": dflt,
                                      "position": pos}))
        finally:
            conn.close()
        return assets

    async def get_asset_details(self, external_id: str) -> Optional[DiscoveredAsset]:
        for a in await self.discover():
            if a.external_id == external_id:
                return a
        return None

    async def get_sample_data(self, external_id: str, limit: int = 10) -> List[Dict]:
        parts = external_id.split(".")
        if len(parts) < 2:
            return []
        table = parts[1]
        conn = await self._connect()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(f"SELECT * FROM `{table}` LIMIT {int(limit)}")
                return list(await cur.fetchall())
        finally:
            conn.close()
