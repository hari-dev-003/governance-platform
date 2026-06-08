"""Celery drift-monitoring tasks."""
from __future__ import annotations

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.monitoring import MonitoringConfig
from app.workers.tasks._util import run_async


@celery_app.task
def run_all_drift_monitors():
    async def _go():
        async with AsyncSessionLocal() as db:
            n = (await db.execute(
                select(MonitoringConfig).where(MonitoringConfig.is_active.is_(True)))).scalars().all()
        # In production each config would pull live predictions from endpoint_url and
        # compute PSI vs. baseline. Here we report how many monitors are active.
        return {"active_monitors": len(n)}
    return run_async(_go())
