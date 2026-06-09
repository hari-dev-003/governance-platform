"""Data Quality - Great Expectations (only engine).

Each QualityRule maps to a Great Expectations expectation evaluated over a pandas
DataFrame built from connector-sampled rows. Robust against GE API differences and
surfaces clear errors instead of failing the whole request.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ConnectorType
from app.connectors.credential_vault import vault
from app.connectors.registry import get_connector
from app.models.assets import Asset
from app.models.quality import QualityCheckResult, QualityCheckRun, QualityRule
from app.models.sources import DataSource

logger = logging.getLogger("governance.quality")


def _ge_dataset(df):
    """Wrap a pandas DataFrame as a Great Expectations dataset (V2 PandasDataset)."""
    try:
        from great_expectations.dataset import PandasDataset
        return PandasDataset(df)
    except Exception:  # noqa: BLE001
        import great_expectations as ge
        return ge.from_pandas(df)


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

    def _evaluate(self, gdf, rule: QualityRule) -> dict:
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
            r = getattr(res, "result", None) or {}
            success = bool(getattr(res, "success", False))
            total = r.get("element_count", 0) or 0
            failed = r.get("unexpected_count", 0) or 0
            return {"status": "passed" if success else "failed",
                    "records_evaluated": total, "records_failed": failed,
                    "failure_percentage": (failed / total * 100) if total else 0.0,
                    "sample_failures": (r.get("partial_unexpected_list") or [])[:10]}
        except Exception as e:  # noqa: BLE001
            logger.warning("quality rule %s failed to evaluate: %s", rule.name, e)
            return {"status": "error", "records_evaluated": 0, "records_failed": 0,
                    "failure_percentage": 0.0, "sample_failures": [{"error": str(e)[:200]}]}

    async def run_for_asset(self, asset: Asset) -> dict:
        rules = list((await self.db.execute(
            select(QualityRule).where(QualityRule.asset_id == asset.id,
                                      QualityRule.is_active.is_(True))
        )).scalars().all())

        if not rules:
            return {"run_id": None, "engine": "great_expectations", "score": None,
                    "total_rules": 0, "passed": 0, "failed": 0,
                    "message": "No active quality rules for this asset. Add rules first."}

        gdf = None
        load_error = None
        try:
            df = await self._sample_df(asset)
            if df is not None and not df.empty:
                gdf = _ge_dataset(df)
        except Exception as e:  # noqa: BLE001
            load_error = str(e)[:200]
            logger.warning("quality: could not sample/load asset %s: %s", asset.name, load_error)

        run = QualityCheckRun(asset_id=asset.id, total_rules=len(rules),
                              run_metadata={"engine": "great_expectations",
                                            "load_error": load_error})
        self.db.add(run)
        await self.db.flush()

        passed = 0
        for rule in rules:
            if gdf is None:
                ev = {"status": "error", "records_evaluated": 0, "records_failed": 0,
                      "failure_percentage": 0.0,
                      "sample_failures": [{"error": load_error or "no sample data"}]}
            else:
                ev = self._evaluate(gdf, rule)
            if ev["status"] == "passed":
                passed += 1
            self.db.add(QualityCheckResult(run_id=run.id, rule_id=rule.id, **ev))

        evaluated = sum(1 for _ in rules)
        score = (passed / evaluated * 100) if evaluated else None
        run.passed_rules = passed
        run.failed_rules = len(rules) - passed
        run.overall_score = score
        asset.quality_score = score
        await self.db.flush()
        result = {"run_id": str(run.id), "engine": "great_expectations", "score": score,
                  "total_rules": len(rules), "passed": passed, "failed": len(rules) - passed}
        if load_error:
            result["message"] = f"Could not load sample data: {load_error}"
        return result

    async def autogenerate_rules(self, asset: Asset, created_by) -> dict:
        """Profile the table and create sensible default rules (no per-column work needed)."""
        import re
        import pandas as pd

        df = await self._sample_df(asset)
        if df is None or df.empty:
            return {"created": 0, "rules": [], "message": "No sample data to profile."}

        existing = list((await self.db.execute(
            select(QualityRule).where(QualityRule.asset_id == asset.id))).scalars().all())
        have = {(r.rule_type, (r.rule_config or {}).get("column")) for r in existing}

        email_rx = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        financial = re.compile(r"amount|price|total|revenue|cost|qty|quantity|count|balance|salary|fee", re.I)
        created = []

        def add(rule_type, dimension, column, cfg):
            if (rule_type, column) in have:
                return
            name = f"{rule_type} {column}"
            self.db.add(QualityRule(org_id=asset.org_id, asset_id=asset.id, created_by=created_by,
                                    name=name, dimension=dimension, rule_type=rule_type,
                                    rule_config={"column": column, **cfg}))
            have.add((rule_type, column))
            created.append({"column": column, "rule_type": rule_type, **cfg})

        n = len(df)
        for col in df.columns:
            series = df[col]
            name = str(col).lower()
            null_count = int(series.isna().sum())
            non_null = n - null_count
            nunique = int(series.nunique(dropna=True))
            is_num = pd.api.types.is_numeric_dtype(series)

            # completeness: column had no nulls in the sample
            if null_count == 0 and non_null > 0:
                add("not_null", "completeness", col, {})
            # uniqueness: id / email / fully-distinct columns
            if non_null > 1 and nunique == non_null and (name == "id" or name.endswith("_id")
                                                         or "email" in name or nunique == n):
                add("unique", "uniqueness", col, {})
            # validity: financial/quantity numerics should be non-negative
            if is_num and financial.search(name):
                add("range", "validity", col, {"min": 0})
            # validity: email format
            if "email" in name:
                add("regex", "validity", col, {"pattern": email_rx})

        await self.db.flush()
        return {"created": len(created), "rules": created}
