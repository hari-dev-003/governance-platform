# Tools by Lifecycle Stage

Every engine below is a **required, core dependency** (installed by `uv sync`) and is the
single real engine for its stage - integrated into the backend, exposed through the platform
API, with results shown only in this platform's UI. Each API response includes an `"engine"`
field so you can confirm which tool produced it.

## Data Governance

| Stage | Tool | Where (backend) | Frontend |
|-------|------|-----------------|----------|
| Cataloging | **Native RDBMS introspection** (no OpenMetadata) - reads `information_schema` directly via asyncpg / aiomysql / aioodbc | `connectors/databases/{postgresql,mysql,mssql}.py`, `services/catalog_service.py` | Sources -> Scan; Catalog |
| Lineage | **sqlglot** + repo connector (any Git/GitHub/local) -> cross-connector resolver | `connectors/etl/parsers.py`, `connectors/etl/repo_connector.py`, `services/lineage_service.py` | Lineage page (Rebuild) |
| Data Quality | **Great Expectations** | `services/quality_service.py` | Quality / Asset Detail |
| Data Privacy | **Microsoft Presidio** (values for RDBMS, names elsewhere) | `services/privacy_service.py` | Privacy (PII) page |

## AI Governance

| Stage | Tool | Where (backend) | Frontend |
|-------|------|-----------------|----------|
| Bias & Fairness | **Fairlearn** (MetricFrame + demographic_parity / equalized_odds) | `services/bias_service.py` | Model Detail -> Bias |
| Explainability | **SHAP** (global) + **LIME** (local) over a sklearn surrogate | `services/explainability_service.py` | Model Detail -> Explainability |
| Model Monitoring | **Evidently AI** (DataDriftPreset) | `services/monitoring_service.py` | Monitoring page |
| Drift Detection | **alibi-detect** (KSDrift, scipy-backed - no TensorFlow at runtime) | `services/drift_service.py` | Monitoring page |

## Native cataloging - supported RDBMS

| Database | Driver | Method |
|----------|--------|--------|
| PostgreSQL | asyncpg (core) | `information_schema` schemas/tables/columns |
| MySQL | aiomysql (core) | `information_schema` tables/columns |
| MS SQL Server | aioodbc (core; also needs a system ODBC driver) | `INFORMATION_SCHEMA` / `sys.*` |

## Install (one command)

```bash
cd backend
uv sync                                        # installs core + all required engines
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl # Presidio NLP model
```

> **All 14 connectors are included** in the core install (databases, lakes, warehouses, ETL,
> model registries, IAM). A connector only ever activates for a **data source you configure
> with credentials** - the registry lazy-loads it on demand (test / scan / quality / privacy);
> unconfigured connectors never load or run.
>
> Only **Celery/Redis** are optional (`uv sync --extra workers`) - background work otherwise
> runs as FastAPI tasks. `alibi-detect` pulls TensorFlow transitively, but drift uses its
> scipy-based `KSDrift`, so TensorFlow is never loaded at runtime.
