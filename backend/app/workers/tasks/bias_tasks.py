"""Celery bias-test tasks (long-running)."""
from __future__ import annotations

from app.core.celery_app import celery_app


@celery_app.task(bind=True)
def run_bias_test(self, bias_test_run_id: str):
    # Placeholder for queueing heavy fairlearn/aif360 runs; the synchronous API
    # path computes metrics inline for interactive use.
    return {"bias_test_run_id": bias_test_run_id, "status": "queued"}
