"""Data Privacy / PII discovery - Microsoft Presidio (only engine).

Per data-source strategy:
  - database / warehouse : Presidio runs over SAMPLED VALUES (most accurate)
  - other (e.g. data lake): Presidio runs over column names (no value access)
  - iam / model_registry : skipped (no personal-data columns)

Detections roll the asset's sensitivity up and are stored in classification_results.
Requires the small spaCy model:  python -m spacy download en_core_web_sm
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector
from app.models.assets import Asset
from app.models.classification import ClassificationResult
from app.models.sources import DataSource

ENTITY_MAP = {
    "EMAIL_ADDRESS": ("PII", "confidential"), "PHONE_NUMBER": ("PII", "confidential"),
    "PERSON": ("PII", "confidential"), "LOCATION": ("PII", "internal"),
    "IP_ADDRESS": ("PII", "internal"), "US_SSN": ("PII", "restricted"),
    "CREDIT_CARD": ("PCI", "restricted"), "IBAN_CODE": ("Financial", "restricted"),
    "US_BANK_NUMBER": ("Financial", "restricted"), "US_PASSPORT": ("PII", "restricted"),
    "US_DRIVER_LICENSE": ("PII", "restricted"), "MEDICAL_LICENSE": ("PHI", "restricted"),
    "DATE_TIME": ("PII", "internal"), "NRP": ("PII", "confidential"),
}
_SENS = ["public", "internal", "confidential", "restricted"]
_SAMPLE_CATEGORIES = {"database", "warehouse"}


def _build_analyzer():
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    cfg = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}
    nlp = NlpEngineProvider(nlp_configuration=cfg).create_engine()
    return AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])


class PrivacyService:
    """Engine: Microsoft Presidio (https://microsoft.github.io/presidio)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._analyzer = None

    def _analyzer_engine(self):
        if self._analyzer is None:
            self._analyzer = _build_analyzer()
        return self._analyzer

    def _bump(self, asset: Asset, sensitivity: str):
        cur = _SENS.index(asset.sensitivity_level) if asset.sensitivity_level in _SENS else 0
        new = _SENS.index(sensitivity) if sensitivity in _SENS else 0
        if new > cur:
            asset.sensitivity_level = sensitivity

    async def _record(self, asset: Asset, entity: str, score: float):
        category, sensitivity = ENTITY_MAP.get(entity, ("PII", "confidential"))
        self.db.add(ClassificationResult(
            asset_id=asset.id, detected_category=f"{category}:{entity}",
            sensitivity_level=sensitivity, confidence_score=round(float(score), 3)))
        self._bump(asset, sensitivity)

    async def scan_source(self, org_id: uuid.UUID, source_id: uuid.UUID) -> dict:
        source = await self.db.get(DataSource, source_id)
        if not source:
            return {"error": "source not found"}
        if source.category in ("iam", "model_registry"):
            return {"strategy": "skipped", "engine": "presidio", "columns_scanned": 0, "findings": 0,
                    "reason": f"{source.category} has no personal-data columns"}

        columns = list((await self.db.execute(
            select(Asset).where(Asset.org_id == org_id, Asset.source_id == source_id,
                                Asset.asset_type == "column")
        )).scalars().all())

        analyzer = self._analyzer_engine()
        use_values = source.category in _SAMPLE_CATEGORIES
        strategy = "presidio_values" if use_values else "presidio_column_names"
        findings = 0
        sample_cache: dict[uuid.UUID, list[dict]] = {}
        conn = None
        if use_values:
            conn = get_connector(ConnectorType(source.connector_type),
                                 {**(source.connection_config or {}), **vault.decrypt(source.encrypted_credentials)})

        for col in columns:
            hits: dict[str, float] = {}
            texts: list[str] = []
            if use_values and col.parent_id:
                if col.parent_id not in sample_cache:
                    parent = await self.db.get(Asset, col.parent_id)
                    try:
                        sample_cache[col.parent_id] = await conn.get_sample_data(parent.external_id, limit=50)
                    except Exception:  # noqa: BLE001
                        sample_cache[col.parent_id] = []
                texts = [str(r.get(col.name)) for r in sample_cache[col.parent_id]
                         if r.get(col.name) not in (None, "")]
            else:
                texts = [col.name.replace("_", " ")]
            for t in texts:
                for res in analyzer.analyze(text=t, language="en"):
                    hits[res.entity_type] = max(hits.get(res.entity_type, 0.0), res.score)
            for entity, score in hits.items():
                if entity in ENTITY_MAP:
                    await self._record(col, entity, score)
                    findings += 1

        await self.db.flush()
        return {"strategy": strategy, "engine": "presidio",
                "columns_scanned": len(columns), "findings": findings}
