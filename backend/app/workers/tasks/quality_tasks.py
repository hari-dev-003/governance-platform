"""Celery quality tasks."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.assets import Asset
from app.models.quality import QualityRule
from app.services.quality_service import QualityService
from app.workers.tasks._util import run_async


@celery_app.task(bind=True, max_retries=3)
def run_quality_checks(self, asset_id: str):
    async def _go():
        async with AsyncSessionLocal() as db:
            asset = await db.get(Asset, uuid.UUID(asset_id))
            if not asset:
                return {"error": "asset not found"}
            res = await QualityService(db).run_for_asset(asset)
            await db.commit()
            return res
    return run_async(_go())


@celery_app.task
def schedule_all_quality_checks():
    async def _go():
        async with AsyncSessionLocal() as db:
            ids = (await db.execute(select(QualityRule.asset_id).distinct())).scalars().all()
        for aid in ids:
            run_quality_checks.delay(str(aid))
        return {"scheduled": len(ids)}
    return run_async(_go())
