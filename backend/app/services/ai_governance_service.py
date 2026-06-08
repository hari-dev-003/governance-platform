"""AI governance — EU AI Act risk scoring and model-card generation."""
from __future__ import annotations

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
