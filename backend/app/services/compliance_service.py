"""Compliance center — framework/requirement seed data and status rollups."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import (
    ComplianceFramework, ComplianceMapping, ComplianceRequirement,
)

SEED_FRAMEWORKS = {
    "GDPR": {
        "version": "2016/679", "description": "EU General Data Protection Regulation",
        "requirements": [
            ("Art. 5", "Principles of processing", "Lawfulness, fairness, transparency, minimisation."),
            ("Art. 15", "Right of access", "Data subjects can access their personal data."),
            ("Art. 17", "Right to erasure", "Right to be forgotten."),
            ("Art. 30", "Records of processing", "Maintain records of processing activities."),
            ("Art. 32", "Security of processing", "Appropriate technical & organisational measures."),
        ],
    },
    "DPDPA": {
        "version": "2023", "description": "India Digital Personal Data Protection Act",
        "requirements": [
            ("S. 5", "Notice", "Provide notice for consent."),
            ("S. 8", "Data fiduciary obligations", "Accuracy, security, retention limits."),
            ("S. 9", "Children's data", "Verifiable consent for minors."),
        ],
    },
    "EU_AI_ACT": {
        "version": "2024", "description": "EU Artificial Intelligence Act",
        "requirements": [
            ("Art. 9", "Risk management system", "For high-risk AI systems.", ["high"]),
            ("Art. 10", "Data & data governance", "Training/validation/testing data quality.", ["high"]),
            ("Art. 13", "Transparency", "Transparency & provision of information.", ["high", "limited"]),
            ("Art. 14", "Human oversight", "Effective human oversight.", ["high"]),
            ("Art. 52", "Transparency obligations", "Disclose AI interaction / labelled content.", ["limited"]),
        ],
    },
    "PCI_DSS": {
        "version": "4.0", "description": "Payment Card Industry Data Security Standard",
        "requirements": [
            ("Req. 3", "Protect stored cardholder data", "Encryption of cardholder data at rest."),
            ("Req. 7", "Restrict access", "Need-to-know access control."),
            ("Req. 10", "Log & monitor", "Track and monitor all access."),
        ],
    },
}


async def seed_frameworks(db: AsyncSession) -> None:
    existing = (await db.execute(select(ComplianceFramework.name))).scalars().all()
    existing_set = set(existing)
    for name, spec in SEED_FRAMEWORKS.items():
        if name in existing_set:
            continue
        fw = ComplianceFramework(name=name, version=spec["version"], description=spec["description"])
        db.add(fw)
        await db.flush()
        for req in spec["requirements"]:
            ref, title, desc = req[0], req[1], req[2]
            tiers = req[3] if len(req) > 3 else None
            db.add(ComplianceRequirement(
                framework_id=fw.id, article_reference=ref, title=title, description=desc,
                requirement_type="both", applies_to_risk_tiers=tiers,
            ))
    await db.flush()


async def status_summary(db: AsyncSession, org_id: uuid.UUID) -> dict:
    rows = (await db.execute(
        select(ComplianceMapping.status, func.count())
        .where(ComplianceMapping.org_id == org_id)
        .group_by(ComplianceMapping.status)
    )).all()
    summary = {status: count for status, count in rows}
    total = sum(summary.values())
    compliant = summary.get("compliant", 0)
    return {"by_status": summary, "total": total,
            "compliance_rate": round(compliant / total, 3) if total else None}
