"""Celery crawl tasks."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.sources import DataSource
from app.services.crawl_service import crawl_source
from app.workers.tasks._util import run_async


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_source_crawl(self, source_id: str):
    async def _go():
        async with AsyncSessionLocal() as db:
            res = await crawl_source(db, uuid.UUID(source_id))
            await db.commit()
            return res
    return run_async(_go())


@celery_app.task
def schedule_all_crawls():
    async def _go():
        async with AsyncSessionLocal() as db:
            ids = (await db.execute(
                select(DataSource.id).where(DataSource.is_active.is_(True)))).scalars().all()
        for sid in ids:
            run_source_crawl.delay(str(sid))
        return {"scheduled": len(ids)}
    return run_async(_go())
