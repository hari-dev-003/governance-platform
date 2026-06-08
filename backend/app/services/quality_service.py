"""Data quality engine powered by Great Expectations.

Each QualityRule maps to a Great Expectations expectation evaluated over a pandas
DataFrame built from connector-sampled rows. Falls back to a built-in evaluator
only if great_expectations is not installed.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector
from app.models.assets import Asset
from app.models.quality import QualityCheckResult, QualityCheckRun, QualityRule
from app.models.sources import DataSource


def _ge_available() -> bool:
    try:
        import great_expectations  # noqa: F401
        return True
    except Exception:
        return False


class QualityService:
    """Engine: Great Expectations (https://greatexpectations.io)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _sample_df(self, asset: Asset, limit: int = 500):
        import pandas as pd
        source = await self.db.get(DataSource, asset.source_id)
        if not source:
            return pd.DataFrame()
        creds = vault.decrypt(source.encrypted_credentials)
        conn = get_connector(ConnectorType(source.connector_type),
                             {**(source.connection_config or {}), **creds})
        rows = await conn.get_sample_data(asset.external_id, limit=limit)
        return pd.DataFrame(rows)

    # ---- Great Expectations evaluation ---------------------------------
    def _evaluate_ge(self, rule: QualityRule, df) -> dict:
        import great_expectations as ge
        gdf = ge.from_pandas(df)
        cfg = rule.rule_config or {}
        col = cfg.get("column")
        rt = rule.rule_type
        try:
            if rt == "not_null":
                res = gdf.expect_column_values_to_not_be_null(col)
            elif rt == "unique":
                res = gdf.expect_column_values_to_be_unique(col)
            elif rt == "regex":
                res = gdf.expect_column_values_to_match_regex(col, cfg.get("pattern", ".*"))
            elif rt == "range":
                res = gdf.expect_column_values_to_be_between(
                    col, min_value=cfg.get("min"), max_value=cfg.get("max"))
            elif rt == "in_set":
                res = gdf.expect_column_values_to_be_in_set(col, cfg.get("values", []))
            else:
                res = gdf.expect_column_to_exist(col)
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "records_evaluated": len(df), "records_failed": 0,
                    "failure_percentage": 0.0, "sample_failures": [{"error": str(e)}]}
        r = res.result or {}
        total = r.get("element_count", len(df)) or 0
        failed = r.get("unexpected_count", 0) or 0
        pct = (failed / total * 100) if total else 0.0
        return {"status": "passed" if res.success else "failed",
                "records_evaluated": total, "records_failed": failed,
                "failure_percentage": pct,
                "sample_failures": (r.get("partial_unexpected_list") or [])[:10]}

    # ---- Built-in fallback ---------------------------------------------
    def _evaluate_builtin(self, rule: QualityRule, df) -> dict:
        import re
        cfg = rule.rule_config or {}
        col = cfg.get("column")
        values = df[col].tolist() if (col and col in df.columns) else []
        total = len(values); failed = 0
        if rule.rule_type == "not_null":
            failed = sum(1 for v in values if v is None or v == "" or (isinstance(v, float) and v != v))
        elif rule.rule_type == "unique":
            seen = set()
            for v in values:
                if v in seen:
                    failed += 1
                seen.add(v)
        elif rule.rule_type == "regex":
            rx = re.compile(cfg.get("pattern", ".*"))
            failed = sum(1 for v in values if v is not None and not rx.match(str(v)))
        elif rule.rule_type == "range":
            lo, hi = cfg.get("min"), cfg.get("max")
            for v in values:
                try:
                    n = float(v)
                    if (lo is not None and n < lo) or (hi is not None and n > hi):
                        failed += 1
                except (TypeError, ValueError):
                    failed += 1
        pct = (failed / total * 100) if total else 0.0
        return {"status": "passed" if failed == 0 else "failed", "records_evaluated": total,
                "records_failed": failed, "failure_percentage": pct, "sample_failures": []}

    async def run_for_asset(self, asset: Asset) -> dict:
        rules = list((await self.db.execute(
            select(QualityRule).where(QualityRule.asset_id == asset.id,
                                      QualityRule.is_active.is_(True))
        )).scalars().all())
        df = await self._sample_df(asset) if rules else None
        engine = "great_expectations" if _ge_available() else "builtin"

        run = QualityCheckRun(asset_id=asset.id, total_rules=len(rules),
                              run_metadata={"engine": engine})
        self.db.add(run)
        await self.db.flush()

        passed = 0
        for rule in rules:
            if df is None or df.empty:
                ev = {"status": "error", "records_evaluated": 0, "records_failed": 0,
                      "failure_percentage": 0.0, "sample_failures": []}
            elif engine == "great_expectations":
                ev = self._evaluate_ge(rule, df)
            else:
                ev = self._evaluate_builtin(rule, df)
            if ev["status"] == "passed":
                passed += 1
            self.db.add(QualityCheckResult(run_id=run.id, rule_id=rule.id, **ev))

        score = (passed / len(rules) * 100) if rules else None
        run.passed_rules = passed
        run.failed_rules = len(rules) - passed
        run.overall_score = score
        asset.quality_score = score
        await self.db.flush()
        return {"run_id": str(run.id), "engine": engine, "score": score,
                "total_rules": len(rules), "passed": passed, "failed": len(rules) - passed}
