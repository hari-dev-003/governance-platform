"""Data privacy / PII discovery powered by Microsoft Presidio.

Per-source strategy (chosen per data-source category):
  - database / warehouse : Presidio NER + pattern recognizers run over SAMPLED VALUES
  - datalake             : value sampling not available -> column-NAME heuristics
  - iam / model_registry : skipped (no personal data columns)

Detections are written to classification_results and roll the asset's sensitivity up.
Falls back to regex name/value heuristics only if presidio is not installed.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector
from app.models.assets import Asset
from app.models.classification import ClassificationResult
from app.models.sources import DataSource

# Presidio entity -> (category, sensitivity)
ENTITY_MAP = {
    "EMAIL_ADDRESS": ("PII", "confidential"),
    "PHONE_NUMBER": ("PII", "confidential"),
    "PERSON": ("PII", "confidential"),
    "LOCATION": ("PII", "internal"),
    "IP_ADDRESS": ("PII", "internal"),
    "US_SSN": ("PII", "restricted"),
    "CREDIT_CARD": ("PCI", "restricted"),
    "IBAN_CODE": ("Financial", "restricted"),
    "US_BANK_NUMBER": ("Financial", "restricted"),
    "US_PASSPORT": ("PII", "restricted"),
    "US_DRIVER_LICENSE": ("PII", "restricted"),
    "MEDICAL_LICENSE": ("PHI", "restricted"),
    "DATE_TIME": ("PII", "internal"),
    "NRP": ("PII", "confidential"),
}
_SENS_ORDER = ["public", "internal", "confidential", "restricted"]

_NAME_RULES = [
    (re.compile(r"email|e-mail", re.I), "EMAIL_ADDRESS"),
    (re.compile(r"phone|mobile|contact", re.I), "PHONE_NUMBER"),
    (re.compile(r"ssn|social_security", re.I), "US_SSN"),
    (re.compile(r"card|credit|pan\b", re.I), "CREDIT_CARD"),
    (re.compile(r"name|surname|fname|lname", re.I), "PERSON"),
    (re.compile(r"iban|account|bank", re.I), "IBAN_CODE"),
    (re.compile(r"address|city|country|zip|postal", re.I), "LOCATION"),
    (re.compile(r"ip_?addr", re.I), "IP_ADDRESS"),
]

_VALUE_SAMPLE_CATEGORIES = {"database", "warehouse"}


def _presidio_engine():
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    cfg = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}
    nlp = NlpEngineProvider(nlp_configuration=cfg).create_engine()
    return AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])


def _presidio_available() -> bool:
    try:
        import presidio_analyzer  # noqa: F401
        return True
    except Exception:
        return False


class PrivacyService:
    """Engine: Microsoft Presidio (https://microsoft.github.io/presidio)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._analyzer = None

    def _analyzer_or_none(self):
        if self._analyzer is None and _presidio_available():
            try:
                self._analyzer = _presidio_engine()
            except Exception:  # noqa: BLE001  (e.g. spaCy model missing)
                self._analyzer = False
        return self._analyzer or None

    def _bump(self, asset: Asset, sensitivity: str):
        cur = _SENS_ORDER.index(asset.sensitivity_level) if asset.sensitivity_level in _SENS_ORDER else 0
        new = _SENS_ORDER.index(sensitivity) if sensitivity in _SENS_ORDER else 0
        if new > cur:
            asset.sensitivity_level = sensitivity

    async def _record(self, asset: Asset, entity: str, confidence: float):
        category, sensitivity = ENTITY_MAP.get(entity, ("PII", "confidential"))
        self.db.add(ClassificationResult(
            asset_id=asset.id, detected_category=f"{category}:{entity}",
            sensitivity_level=sensitivity, confidence_score=round(confidence, 3),
        ))
        self._bump(asset, sensitivity)

    async def scan_source(self, org_id: uuid.UUID, source_id: uuid.UUID) -> dict:
        source = await self.db.get(DataSource, source_id)
        if not source:
            return {"error": "source not found"}

        columns = list((await self.db.execute(
            select(Asset).where(Asset.org_id == org_id, Asset.source_id == source_id,
                                Asset.asset_type == "column")
        )).scalars().all())

        if source.category in ("iam", "model_registry"):
            return {"strategy": "skipped", "reason": f"{source.category} has no personal-data columns",
                    "columns_scanned": 0, "findings": 0}

        analyzer = self._analyzer_or_none()
        use_values = source.category in _VALUE_SAMPLE_CATEGORIES and analyzer is not None

        findings = 0
        strategy = "presidio_values" if use_values else ("presidio_names" if analyzer else "regex_names")

        # cache sampled rows per parent table to avoid re-sampling
        sample_cache: dict[uuid.UUID, list[dict]] = {}
        if use_values:
            conn = get_connector(ConnectorType(source.connector_type),
                                 {**(source.connection_config or {}), **vault.decrypt(source.encrypted_credentials)})

        for col in columns:
            entity_hits: dict[str, float] = {}
            if use_values and col.parent_id:
                if col.parent_id not in sample_cache:
                    parent = await self.db.get(Asset, col.parent_id)
                    try:
                        sample_cache[col.parent_id] = await conn.get_sample_data(parent.external_id, limit=50)
                    except Exception:  # noqa: BLE001
                        sample_cache[col.parent_id] = []
                for row in sample_cache[col.parent_id]:
                    val = row.get(col.name)
                    if val in (None, ""):
                        continue
                    for res in analyzer.analyze(text=str(val), language="en"):
                        entity_hits[res.entity_type] = max(entity_hits.get(res.entity_type, 0), res.score)
            else:
                # name-based heuristics
                for rx, entity in _NAME_RULES:
                    if rx.search(col.name):
                        entity_hits[entity] = 0.6

            for entity, score in entity_hits.items():
                if entity in ENTITY_MAP:
                    await self._record(col, entity, score)
                    findings += 1

        await self.db.flush()
        return {"strategy": strategy, "engine": "presidio" if analyzer else "regex",
                "columns_scanned": len(columns), "findings": findings}
