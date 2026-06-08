"""Aggregate all v1 routers under a single APIRouter."""
from fastapi import APIRouter

from app.api.v1 import (
    access_requests, assets, audit, auth, ai_models, bias_testing, classification,
    compliance, dashboard, explainability, glossary, lineage, monitoring, policies,
    privacy, quality, risk_assessment, sources,
)

api_router = APIRouter()
for module in (
    auth, sources, assets, lineage, glossary, classification, quality, policies,
    access_requests, ai_models, risk_assessment, bias_testing, explainability,
    monitoring, compliance, audit, dashboard, privacy,
):
    api_router.include_router(module.router)
