"""
End-to-end acceptance test - run on your machine (with the full uv environment).

It exercises every Data + AI Governance stage with the REAL engines against your
Postgres, and verifies every connector SDK is installed. Prints PASS/FAIL + engine.

Usage (from backend/, with your Postgres running and .env configured):
    uv run python scripts/acceptance_test.py
"""
from __future__ import annotations

import asyncio
import importlib
import uuid

OK = "\033[92mPASS\033[0m"
NO = "\033[91mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []


def log(stage: str, ok: bool, detail: str = ""):
    results.append((stage, ok, detail))
    print(f"  [{OK if ok else NO}] {stage:32} {detail}")


async def main():
    from app.core.database import AsyncSessionLocal, Base, engine
    from app.core.config import settings
    import app.models  # noqa
    from app.models.identity import Organization, User
    from app.models.sources import DataSource
    from app.models.assets import Asset
    from app.models.quality import QualityRule
    from app.connectors.credential_vault import vault
    from app.connectors.base import ConnectorType, CONNECTOR_CATEGORY
    from app.connectors.registry import list_connector_types
    from app.services.bootstrap import run_bootstrap
    from app.services.crawl_service import crawl_source
    from app.services.classification_service import ClassificationService
    from app.services.privacy_service import PrivacyService
    from app.services.quality_service import QualityService
    from app.services.ai_governance_service import assess_risk
    from app.services.bias_service import compute_group_metrics
    from app.services.explainability_service import explain
    from app.services.drift_service import detect_drift
    from app.services.monitoring_service import data_drift_report
    from app.services.compliance_service import status_summary
    from app.services.dashboard_service import overview
    from sqlalchemy import select

    print("\n=== 0. Schema + bootstrap ===")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await run_bootstrap(db)
    log("DB schema + seed", True, "tables created, admin/org/rules/frameworks seeded")

    async with AsyncSessionLocal() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == settings.DEFAULT_ORG_SLUG))).scalar_one()
        admin = (await db.execute(select(User).where(User.org_id == org.id))).scalars().first()

        # ---- 1. Native cataloging: connect to YOUR Postgres and crawl ----
        print("\n=== 1. Data Governance ===")
        src = DataSource(
            org_id=org.id, name="Acceptance PG", connector_type="postgresql", category="database",
            encrypted_credentials=vault.encrypt({"password": settings.DB_PASSWORD}),
            connection_config={"host": settings.DB_HOST, "port": int(settings.DB_PORT),
                               "database": settings.DB_NAME, "username": settings.DB_USER},
            created_by=admin.id)
        db.add(src); await db.flush()
        try:
            res = await crawl_source(db, src.id); await db.commit()
            log("Cataloging (native RDBMS)", res.get("assets_discovered", 0) > 0,
                f"discovered {res.get('assets_discovered')} assets")
        except Exception as e:
            log("Cataloging (native RDBMS)", False, str(e)[:60])

        try:
            r = await ClassificationService(db).classify_source_columns(org.id, src.id); await db.commit()
            log("Classification (regex/keyword)", True, f"{r['classifications']} hits / {r['columns_scanned']} cols")
        except Exception as e:
            log("Classification", False, str(e)[:60])

        try:
            r = await PrivacyService(db).scan_source(org.id, src.id); await db.commit()
            log("Privacy (Presidio)", r.get("engine") == "presidio",
                f"engine={r.get('engine')} strategy={r.get('strategy')} findings={r.get('findings')}")
        except Exception as e:
            log("Privacy (Presidio)", False, str(e)[:80])

        # quality: add a not_null rule on a column of the first table, then run GE
        try:
            table = (await db.execute(select(Asset).where(Asset.org_id == org.id, Asset.asset_type == "table").limit(1))).scalar_one()
            col = (await db.execute(select(Asset).where(Asset.parent_id == table.id).limit(1))).scalar_one()
            db.add(QualityRule(org_id=org.id, asset_id=table.id, created_by=admin.id, name="not null",
                               dimension="completeness", rule_type="not_null", rule_config={"column": col.name}))
            await db.flush()
            r = await QualityService(db).run_for_asset(table); await db.commit()
            log("Data Quality (Great Expectations)", r.get("engine") == "great_expectations",
                f"engine={r.get('engine')} score={r.get('score')}")
        except Exception as e:
            log("Data Quality (Great Expectations)", False, str(e)[:80])

        # ---- 2. AI Governance ----
        print("\n=== 2. AI Governance ===")
        try:
            risk = assess_risk({"essential_services": True, "human_interaction": True})
            log("Risk (EU AI Act)", risk["risk_tier"] in ("high", "limited", "minimal", "unacceptable"),
                f"tier={risk['risk_tier']} actions={len(risk['required_actions'])}")
        except Exception as e:
            log("Risk (EU AI Act)", False, str(e)[:60])

        recs = [{"gender": "M", "label": "1", "prediction": "1"}, {"gender": "M", "label": "0", "prediction": "1"},
                {"gender": "M", "label": "1", "prediction": "1"}, {"gender": "F", "label": "1", "prediction": "0"},
                {"gender": "F", "label": "0", "prediction": "0"}, {"gender": "F", "label": "1", "prediction": "0"}]
        try:
            b = compute_group_metrics(recs, "gender", "label", "prediction", "1")
            log("Bias (Fairlearn)", b.get("engine") == "fairlearn", f"engine={b['engine']} verdict={b['verdict']}")
        except Exception as e:
            log("Bias (Fairlearn)", False, str(e)[:80])

        try:
            data = [{"income": i, "debt": i % 30, "credit": (i * 3) % 50,
                     "label": 1 if (i - (i % 30)) > 20 else 0} for i in range(60)]
            x = explain(data, "label", 0)
            log("Explainability (SHAP+LIME)", x.get("engine") == "shap+lime",
                f"engine={x['engine']} top={x['global_importance'][0]['feature'] if x.get('global_importance') else '-'}")
        except Exception as e:
            log("Explainability (SHAP+LIME)", False, str(e)[:80])

        try:
            d = detect_drift([float(i) for i in range(1, 41)], [float(i) for i in range(20, 60)])
            log("Drift (alibi-detect KSDrift)", "alibi-detect" in d.get("engine", ""),
                f"engine={d['engine']} drift={d['drift']}")
        except Exception as e:
            log("Drift (alibi-detect)", False, str(e)[:80])

        try:
            ref = [{"x": float(i), "y": float(i % 7)} for i in range(60)]
            cur = [{"x": float(i + 25), "y": float(i % 7)} for i in range(60)]
            ev = data_drift_report(ref, cur)
            log("Monitoring (Evidently)", ev.get("engine") == "evidently",
                f"engine={ev['engine']} dataset_drift={ev.get('dataset_drift')}")
        except Exception as e:
            log("Monitoring (Evidently)", False, str(e)[:80])

        # ---- 3. Compliance + dashboard ----
        print("\n=== 3. Compliance + Dashboard ===")
        try:
            cs = await status_summary(db, org.id)
            ov = await overview(db, org.id)
            log("Compliance + Dashboard", True,
                f"assets={ov['total_assets']} models={ov['ai_models']} frameworks seeded")
        except Exception as e:
            log("Compliance + Dashboard", False, str(e)[:60])

    # ---- 4. All connectors installed & wired ----
    print("\n=== 4. Connectors (SDK installed + registered) ===")
    sdk = {"postgresql": "asyncpg", "mysql": "aiomysql", "mssql": "aioodbc", "aws_s3": "boto3",
           "azure_blob": "azure.storage.blob", "bigquery": "google.cloud.bigquery", "redshift": "asyncpg",
           "github_etl": "github", "mlflow": "mlflow", "sagemaker": "boto3",
           "azure_ml": "azure.ai.ml", "vertex_ai": "google.cloud.aiplatform",
           "aws_iam": "boto3", "keycloak": "keycloak"}
    for ct in list_connector_types():
        mod = sdk.get(ct, "")
        try:
            importlib.import_module(mod)
            log(f"connector:{ct}", True, f"SDK '{mod}' installed, category={CONNECTOR_CATEGORY[ConnectorType(ct)]}")
        except Exception:
            log(f"connector:{ct}", False, f"SDK '{mod}' NOT installed")

    # ---- summary ----
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{total} checks passed")
    print("=" * 60)
    if passed == total:
        print("✅ Fully operational end-to-end - every stage and connector verified.")
    else:
        print("⚠️  Some checks failed (see FAIL lines above).")
        for s, ok, d in results:
            if not ok:
                print(f"   - {s}: {d}")


if __name__ == "__main__":
    asyncio.run(main())
