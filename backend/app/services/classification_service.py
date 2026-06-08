"""Data classification — applies regex/keyword rules to columns to detect PII etc."""
from __future__ import annotations

import re
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector
from app.models.assets import Asset
from app.models.classification import ClassificationResult, ClassificationRule
from app.models.sources import DataSource

# Highest sensitivity wins when several rules match the same asset.
_SENSITIVITY_ORDER = ["public", "internal", "confidential", "restricted"]


def _max_sensitivity(levels: List[str]) -> str:
    idx = max((_SENSITIVITY_ORDER.index(l) for l in levels if l in _SENSITIVITY_ORDER), default=0)
    return _SENSITIVITY_ORDER[idx]


class ClassificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _active_rules(self, org_id: uuid.UUID) -> list[ClassificationRule]:
        return list((await self.db.execute(
            select(ClassificationRule).where(
                ClassificationRule.org_id == org_id, ClassificationRule.is_active.is_(True)
            )
        )).scalars().all())

    def _match(self, rule: ClassificationRule, text: str, samples: list[str]) -> bool:
        hay = " ".join([text] + [str(s) for s in samples]).lower()
        if rule.detection_method == "keyword" and rule.keywords:
            return any(k.lower() in hay for k in rule.keywords)
        if rule.detection_method == "regex" and rule.pattern:
            try:
                rx = re.compile(rule.pattern, re.IGNORECASE)
            except re.error:
                return False
            return bool(rx.search(text) or any(rx.search(str(s)) for s in samples))
        return False

    async def classify_asset(self, asset: Asset) -> list[dict]:
        rules = await self._active_rules(asset.org_id)
        # gather sample values for column assets
        samples: list[str] = []
        if asset.asset_type == "column":
            try:
                source = await self.db.get(DataSource, asset.source_id)
                if source:
                    creds = vault.decrypt(source.encrypted_credentials)
                    conn = get_connector(ConnectorType(source.connector_type),
                                         {**(source.connection_config or {}), **creds})
                    parent_ext = asset.technical_metadata.get("_parent_external_id")
                    table_ext = ".".join(asset.external_id.split(".")[:-1])
                    rows = await conn.get_sample_data(table_ext, limit=20)
                    col = asset.name
                    samples = [str(r.get(col)) for r in rows if isinstance(r, dict) and col in r]
            except Exception:  # noqa: BLE001
                samples = []

        hits = []
        matched_levels = []
        for rule in rules:
            if self._match(rule, asset.name, samples):
                res = ClassificationResult(
                    asset_id=asset.id, rule_id=rule.id, detected_category=rule.category,
                    sensitivity_level=rule.sensitivity_level, confidence_score=0.9,
                )
                self.db.add(res)
                matched_levels.append(rule.sensitivity_level)
                hits.append({"rule": rule.name, "category": rule.category,
                             "sensitivity": rule.sensitivity_level})
        if matched_levels:
            asset.sensitivity_level = _max_sensitivity(matched_levels)
        await self.db.flush()
        return hits

    async def classify_source_columns(self, org_id: uuid.UUID, source_id: uuid.UUID) -> dict:
        cols = (await self.db.execute(
            select(Asset).where(Asset.org_id == org_id, Asset.source_id == source_id,
                                Asset.asset_type == "column")
        )).scalars().all()
        total_hits = 0
        for c in cols:
            total_hits += len(await self.classify_asset(c))
        return {"columns_scanned": len(cols), "classifications": total_hits}
