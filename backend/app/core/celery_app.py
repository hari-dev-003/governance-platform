"""Celery application — broker/result backend on Redis."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "governance",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.tasks.crawler_tasks",
        "app.workers.tasks.quality_tasks",
        "app.workers.tasks.monitoring_tasks",
        "app.workers.tasks.bias_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_max_tasks_per_child=200,
)

celery_app.conf.beat_schedule = {
    "crawl-all-active-sources": {
        "task": "app.workers.tasks.crawler_tasks.schedule_all_crawls",
        "schedule": crontab(hour=2, minute=0),
    },
    "run-scheduled-quality-checks": {
        "task": "app.workers.tasks.quality_tasks.schedule_all_quality_checks",
        "schedule": crontab(hour=3, minute=0),
    },
    "run-drift-monitoring": {
        "task": "app.workers.tasks.monitoring_tasks.run_all_drift_monitors",
        "schedule": crontab(minute="*/30"),
    },
}
