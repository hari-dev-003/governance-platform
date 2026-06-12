"""Backwards-compatible re-export.

Registry sync lives in ``ai_governance_service.sync_models_from_source``; this
module re-exports it so either import path works.
"""
from app.services.ai_governance_service import sync_models_from_source  # noqa: F401
