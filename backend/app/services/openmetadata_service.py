"""Publish discovered assets into OpenMetadata (cataloging system-of-record)."""
from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.openmetadata import OpenMetadataClient, SERVICE_TYPE
from app.models.assets import Asset
from app.models.sources import DataSource


async def publish_source(db: AsyncSession, org_id: uuid.UUID, source_id: uuid.UUID) -> dict:
    source = await db.get(DataSource, source_id)
    if not source:
        return {"error": "source not found"}
    service_type = SERVICE_TYPE.get(source.connector_type)
    if not service_type:
        return {"error": f"OpenMetadata publishing supports relational sources only "
                         f"({', '.join(SERVICE_TYPE)}); '{source.connector_type}' skipped"}

    assets = list((await db.execute(
        select(Asset).where(Asset.org_id == org_id, Asset.source_id == source_id)
    )).scalars().all())
    by_id = {a.id: a for a in assets}

    schemas = [a for a in assets if a.asset_type == "schema"]
    tables = [a for a in assets if a.asset_type == "table"]
    cols_by_table = defaultdict(list)
    for a in assets:
        if a.asset_type == "column" and a.parent_id:
            cols_by_table[a.parent_id].append(a)

    client = OpenMetadataClient()
    service_name = source.name.replace(" ", "_")
    published = {"service": service_name, "schemas": 0, "tables": 0, "columns": 0, "errors": []}
    try:
        client.upsert_database_service(service_name, service_type)
        db_name = (source.connection_config or {}).get("database", "default")
        client.upsert_database(db_name, service_name)
        db_fqn = f"{service_name}.{db_name}"

        for sc in schemas:
            try:
                client.upsert_schema(sc.name, db_fqn)
                published["schemas"] += 1
            except Exception as e:  # noqa: BLE001
                published["errors"].append(f"schema {sc.name}: {e}")
        for tb in tables:
            parent = by_id.get(tb.parent_id)
            schema_name = parent.name if parent else "public"
            schema_fqn = f"{db_fqn}.{schema_name}"
            cols = [{"name": c.name, "data_type": (c.technical_metadata or {}).get("data_type")}
                    for c in cols_by_table.get(tb.id, [])]
            try:
                client.upsert_table(tb.name, schema_fqn, cols)
                published["tables"] += 1
                published["columns"] += len(cols)
            except Exception as e:  # noqa: BLE001
                published["errors"].append(f"table {tb.name}: {e}")
    finally:
        client.close()
    return published
