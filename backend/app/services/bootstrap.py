"""First-run bootstrap: default org, admin user, system classification rules, frameworks."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.classification import ClassificationRule
from app.models.identity import Organization, User
from app.services.compliance_service import seed_frameworks

SYSTEM_RULES = [
    ("Email Address", "PII", "confidential", "regex",
     r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", None),
    ("US SSN", "PII", "restricted", "regex", r"\b\d{3}-\d{2}-\d{4}\b", None),
    ("Credit Card", "PCI", "restricted", "regex", r"\b(?:\d[ -]*?){13,16}\b", None),
    ("Phone Number", "PII", "confidential", "regex", r"\b\+?\d[\d -]{7,}\d\b", None),
    ("IP Address", "PII", "internal", "regex", r"\b\d{1,3}(\.\d{1,3}){3}\b", None),
    ("Name Columns", "PII", "confidential", "keyword", None,
     ["first_name", "last_name", "full_name", "surname", "fname", "lname"]),
    ("Health / PHI", "PHI", "restricted", "keyword", None,
     ["diagnosis", "icd10", "patient", "medical", "treatment", "prescription"]),
    ("Financial", "Financial", "confidential", "keyword", None,
     ["salary", "income", "account_number", "iban", "balance", "revenue"]),
]


async def run_bootstrap(db: AsyncSession) -> None:
    # 1. default org
    org = (await db.execute(
        select(Organization).where(Organization.slug == settings.DEFAULT_ORG_SLUG)
    )).scalar_one_or_none()
    if org is None:
        org = Organization(name=settings.DEFAULT_ORG_NAME, slug=settings.DEFAULT_ORG_SLUG,
                           plan="enterprise")
        db.add(org)
        await db.flush()

    # 2. admin user (only if there are no users at all)
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    if user_count == 0:
        db.add(User(
            org_id=org.id, email=settings.ADMIN_EMAIL, full_name="Platform Admin",
            password_hash=hash_password(settings.ADMIN_PASSWORD), role="admin",
        ))
        await db.flush()

    # 3. system classification rules for the org
    have = (await db.execute(
        select(func.count()).select_from(ClassificationRule)
        .where(ClassificationRule.org_id == org.id, ClassificationRule.is_system_rule.is_(True))
    )).scalar() or 0
    if have == 0:
        for name, cat, sens, method, pattern, keywords in SYSTEM_RULES:
            db.add(ClassificationRule(
                org_id=org.id, name=name, category=cat, sensitivity_level=sens,
                detection_method=method, pattern=pattern, keywords=keywords,
                is_system_rule=True, is_active=True,
            ))
        await db.flush()

    # 4. compliance frameworks (global)
    await seed_frameworks(db)
    await db.commit()
