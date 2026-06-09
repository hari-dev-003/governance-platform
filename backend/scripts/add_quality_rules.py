"""
Create + run Great Expectations quality rules on the sample_shop source.

Run AFTER you've added the sample_shop Postgres source in the UI and clicked Scan.
    uv run python scripts/add_quality_rules.py

It adds representative rules (matching the deliberate issues seeded by sample_data.sql)
and runs them, printing the engine + pass/fail so you can confirm Great Expectations works.
The scores then also appear in the UI (Quality page / Asset Detail).
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

RULES = [
    # (table, name, dimension, rule_type, rule_config)
    ("customers", "email not null", "completeness", "not_null", {"column": "email"}),
    ("customers", "email unique", "uniqueness", "unique", {"column": "email"}),
    ("orders", "total_amount >= 0", "validity", "range", {"column": "total_amount", "min": 0}),
    ("orders", "status not null", "completeness", "not_null", {"column": "status"}),
]


async def main():
    from app.core.database import AsyncSessionLocal
    from app.models.identity import Organization, User
    from app.models.sources import DataSource
    from app.models.assets import Asset
    from app.models.quality import QualityRule
    from app.services.quality_service import QualityService

    async with AsyncSessionLocal() as db:
        org = (await db.execute(select(Organization))).scalars().first()
        admin = (await db.execute(select(User).where(User.org_id == org.id))).scalars().first()

        # find the source pointing at the sample_shop database
        sources = (await db.execute(select(DataSource).where(DataSource.org_id == org.id))).scalars().all()
        src = next((s for s in sources if (s.connection_config or {}).get("database") == "sample_shop"), None)
        if not src:
            print("Could not find a source with database 'sample_shop'. "
                  "Add it in the UI and run Scan first.")
            return

        for table_name, name, dim, rtype, cfg in RULES:
            table = (await db.execute(select(Asset).where(
                Asset.org_id == org.id, Asset.source_id == src.id,
                Asset.asset_type == "table", Asset.name == table_name))).scalars().first()
            if not table:
                print(f"  (table '{table_name}' not found - did you Scan?)")
                continue
            # avoid duplicate rule
            exists = (await db.execute(select(QualityRule).where(
                QualityRule.asset_id == table.id, QualityRule.name == name))).scalars().first()
            if not exists:
                db.add(QualityRule(org_id=org.id, asset_id=table.id, created_by=admin.id,
                                   name=name, dimension=dim, rule_type=rtype, rule_config=cfg))
        await db.commit()

        # run quality per table
        for table_name in ("customers", "orders"):
            table = (await db.execute(select(Asset).where(
                Asset.org_id == org.id, Asset.source_id == src.id,
                Asset.asset_type == "table", Asset.name == table_name))).scalars().first()
            if not table:
                continue
            result = await QualityService(db).run_for_asset(table)
            await db.commit()
            print(f"\n{table_name}: engine={result['engine']} score={result['score']} "
                  f"passed={result['passed']} failed={result['failed']}")
    print("\nDone. Open the Quality page in the UI to see the scores.")


if __name__ == "__main__":
    asyncio.run(main())
