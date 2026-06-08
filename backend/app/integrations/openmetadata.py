"""OpenMetadata cataloging integration (REST API client).

Publishes the platform's discovered assets into OpenMetadata as the system-of-record
catalog: DatabaseService -> Database -> DatabaseSchema -> Table(+Columns), plus lineage.
Uses the OpenMetadata REST API directly (httpx) so the heavy ingestion SDK is not required.

Configure via env: OPENMETADATA_URL, OPENMETADATA_JWT_TOKEN, OPENMETADATA_ENABLED.
"""
from __future__ import annotations

from typing import List, Optional

import httpx

from app.core.config import settings

# our connector_type -> OpenMetadata serviceType
SERVICE_TYPE = {
    "postgresql": "Postgres", "mssql": "Mssql", "redshift": "Redshift", "bigquery": "BigQuery",
}
# crude SQL type -> OpenMetadata column dataType enum
def _omd_dtype(raw: str) -> str:
    r = (raw or "").lower()
    if "int" in r: return "BIGINT" if "big" in r else "INT"
    if "char" in r or "text" in r or "uuid" in r: return "VARCHAR"
    if "bool" in r: return "BOOLEAN"
    if "time" in r or "date" in r: return "TIMESTAMP"
    if "float" in r or "double" in r or "numeric" in r or "decimal" in r or "real" in r: return "DECIMAL"
    if "json" in r: return "JSON"
    return "VARCHAR"


class OpenMetadataClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base = (base_url or settings.OPENMETADATA_URL or "").rstrip("/")
        self.token = token or settings.OPENMETADATA_JWT_TOKEN
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.Client(base_url=self.base, headers=headers, timeout=30)

    def _put(self, path: str, payload: dict) -> dict:
        r = self._client.put(path, json=payload)
        r.raise_for_status()
        return r.json()

    def upsert_database_service(self, name: str, service_type: str) -> dict:
        return self._put("/v1/services/databaseServices", {
            "name": name, "serviceType": service_type,
            "connection": {"config": {"type": service_type}},
        })

    def upsert_database(self, name: str, service_fqn: str) -> dict:
        return self._put("/v1/databases", {"name": name, "service": service_fqn})

    def upsert_schema(self, name: str, database_fqn: str) -> dict:
        return self._put("/v1/databaseSchemas", {"name": name, "database": database_fqn})

    def upsert_table(self, name: str, schema_fqn: str, columns: List[dict]) -> dict:
        return self._put("/v1/tables", {
            "name": name, "databaseSchema": schema_fqn,
            "columns": [{"name": c["name"], "dataType": _omd_dtype(c.get("data_type"))} for c in columns],
        })

    def add_lineage(self, from_table_fqn: str, to_table_fqn: str) -> dict:
        return self._put("/v1/lineage", {
            "edge": {
                "fromEntity": {"type": "table", "fqn": from_table_fqn},
                "toEntity": {"type": "table", "fqn": to_table_fqn},
            }
        })

    def close(self):
        self._client.close()


def is_enabled() -> bool:
    return bool(settings.OPENMETADATA_ENABLED and settings.OPENMETADATA_URL)
