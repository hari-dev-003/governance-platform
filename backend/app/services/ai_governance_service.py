"""AI governance — EU AI Act risk scoring, model-card generation, registry sync."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_models import AIModel, AIModelVersion
from app.models.assets import Asset

# A compact EU-AI-Act-inspired questionnaire. Each answer carries a weight; the
# aggregate maps to a risk tier with mandated follow-up actions.
RISK_QUESTIONS = [
    {"key": "prohibited_use", "text": "Used for social scoring, real-time biometric ID, or manipulation?",
     "weight": 100},
    {"key": "safety_component", "text": "Acts as a safety component of a regulated product?", "weight": 40},
    {"key": "biometric", "text": "Performs biometric identification or categorisation?", "weight": 35},
    {"key": "critical_infra", "text": "Manages critical infrastructure (energy, transport, water)?", "weight": 35},
    {"key": "education_employment", "text": "Affects education, hiring, or worker management?", "weight": 30},
    {"key": "essential_services", "text": "Determines access to essential services / credit?", "weight": 30},
    {"key": "law_enforcement", "text": "Used in law enforcement or migration/border control?", "weight": 35},
    {"key": "justice", "text": "Assists in administration of justice / democratic processes?", "weight": 30},
    {"key": "human_interaction", "text": "Interacts directly with humans (chatbot, etc.)?", "weight": 10},
    {"key": "generates_content", "text": "Generates synthetic content (text/image/audio/video)?", "weight": 10},
]


def assess_risk(responses: dict) -> dict:
    """Map questionnaire (key -> bool) to a risk tier + required actions."""
    if responses.get("prohibited_use"):
        return {
            "risk_tier": "unacceptable",
            "eu_ai_act_category": "Prohibited practice (Art. 5)",
            "risk_factors": ["Prohibited use case under the EU AI Act"],
            "required_actions": ["Do not deploy. Prohibited under EU AI Act Article 5."],
            "score": 100,
        }
    score = sum(q["weight"] for q in RISK_QUESTIONS if responses.get(q["key"]))
    factors = [q["text"] for q in RISK_QUESTIONS if responses.get(q["key"])]

    if score >= 30:
        tier, cat = "high", "High-risk AI system (Annex III)"
        actions = [
            "Establish a risk-management system (Art. 9)",
            "Ensure data governance & quality of training data (Art. 10)",
            "Maintain technical documentation (Art. 11)",
            "Enable record-keeping / logging (Art. 12)",
            "Provide transparency & human oversight (Art. 13-14)",
            "Run a conformity assessment before deployment (Art. 43)",
        ]
    elif responses.get("human_interaction") or responses.get("generates_content"):
        tier, cat = "limited", "Limited-risk (transparency obligations)"
        actions = ["Disclose AI interaction to users", "Label AI-generated content (Art. 52)"]
    else:
        tier, cat = "minimal", "Minimal-risk"
        actions = ["Voluntary codes of conduct; no mandatory obligations"]

    return {"risk_tier": tier, "eu_ai_act_category": cat, "risk_factors": factors,
            "required_actions": actions, "score": score}


def model_card(model: dict, versions: list[dict], assessment: dict | None) -> dict:
    """Assemble a structured model card."""
    return {
        "name": model.get("name"),
        "description": model.get("description"),
        "owner": model.get("owner"),
        "use_case": model.get("use_case"),
        "business_domain": model.get("business_domain"),
        "framework": model.get("framework"),
        "model_type": model.get("model_type"),
        "risk_tier": model.get("risk_tier"),
        "deployment_status": model.get("deployment_status"),
        "versions": versions,
        "risk_assessment": assessment,
        "intended_use": model.get("use_case"),
        "ethical_considerations": (assessment or {}).get("risk_factors", []),
    }


# ---------------------------------------------------------------------------
# Registry sync: promote crawled ml_model / ml_model_version assets (MLflow,
# SageMaker, Vertex, Azure ML) from the catalog into the AI model registry.
# ---------------------------------------------------------------------------
def _meta_get(meta: dict, *keys, default=None):
    for k in keys:
        if isinstance(meta, dict) and meta.get(k) not in (None, ""):
            return meta[k]
    return default


async def sync_models_from_source(db: AsyncSession, org_id: uuid.UUID,
                                  source_id: uuid.UUID) -> dict:
    """Upsert AIModel/AIModelVersion rows from the source's discovered model assets.

    Reads Asset rows of type ``ml_model`` / ``ml_model_version`` (written by the
    model-registry crawlers) and mirrors them into the governance registry,
    carrying source_id, metrics, hyperparameters and artifact/version ids. Safe to
    re-run: it matches on (org_id, external_id) for models and (model_id,
    version_number) for versions.
    """
    assets = list((await db.execute(
        select(Asset).where(
            Asset.org_id == org_id, Asset.source_id == source_id,
            Asset.asset_type.in_(("ml_model", "ml_model_version")),
        )
    )).scalars().all())

    model_assets = [a for a in assets if a.asset_type == "ml_model"]
    version_assets = [a for a in assets if a.asset_type == "ml_model_version"]

    # external_id of the parent ml_model asset -> AIModel row
    ext_to_model: dict[str, AIModel] = {}
    models_synced = 0
    for a in model_assets:
        meta = a.technical_metadata or {}
        existing = (await db.execute(
            select(AIModel).where(AIModel.org_id == org_id, AIModel.external_id == a.external_id)
        )).scalar_one_or_none()
        if existing is None:
            existing = AIModel(org_id=org_id, external_id=a.external_id, name=a.name)
            db.add(existing)
            models_synced += 1
        existing.source_id = source_id
        existing.name = a.name
        existing.description = _meta_get(meta, "description") or existing.description
        existing.framework = _meta_get(meta, "framework",
                                       default=_meta_get(meta.get("tags", {}) or {}, "framework")) or existing.framework
        existing.model_type = _meta_get(meta, "model_type",
                                        default=_meta_get(meta.get("tags", {}) or {}, "model_type")) or existing.model_type
        await db.flush()
        ext_to_model[a.external_id] = existing

    # map a version asset's parent (Asset.id) back to its ml_model external_id
    asset_id_to_ext = {a.id: a.external_id for a in model_assets}

    versions_synced = 0
    for a in version_assets:
        meta = a.technical_metadata or {}
        parent_ext = asset_id_to_ext.get(a.parent_id)
        model = ext_to_model.get(parent_ext)
        if model is None:
            continue
        version_number = str(_meta_get(meta, "version", default=a.external_id.rsplit("/", 1)[-1]))
        run = meta.get("run_details") or {}
        existing = (await db.execute(
            select(AIModelVersion).where(
                AIModelVersion.model_id == model.id,
                AIModelVersion.version_number == version_number,
            )
        )).scalar_one_or_none()
        if existing is None:
            existing = AIModelVersion(model_id=model.id, version_number=version_number)
            db.add(existing)
            versions_synced += 1
        existing.external_version_id = a.external_id
        existing.metrics = run.get("metrics") or existing.metrics or {}
        existing.hyperparameters = run.get("params") or existing.hyperparameters or {}
        existing.stage = _meta_get(meta, "stage", default=existing.stage or "development")
        await db.flush()

    return {"source_id": str(source_id), "models_synced": models_synced,
            "versions_synced": versions_synced,
            "models_total": len(model_assets), "versions_total": len(version_assets)}
