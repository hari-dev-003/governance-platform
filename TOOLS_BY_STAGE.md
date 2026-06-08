# Tools by Lifecycle Stage

The specific engine for each stage. Every engine is integrated via its real API and
lazy-loaded; install `requirements-governance.txt` to activate them. Until then, a
built-in fallback keeps the same endpoint working (the response reports which engine ran).

## Data Governance

| Stage | Tool | Where (backend) | Frontend |
|-------|------|-----------------|----------|
| Cataloging | **OpenMetadata** (REST API) | `integrations/openmetadata.py`, `services/openmetadata_service.py`; `POST /sources/{id}/publish-openmetadata` | Sources -> "OpenMetadata" button |
| Lineage | **sqlglot** (backend) + **React Flow** (frontend) | `connectors/etl/github_etl.py`, `services/lineage_service.py` | Lineage page (React Flow) |
| Data Quality | **Great Expectations** | `services/quality_service.py` (`from_pandas` + expectations) | Quality / Asset Detail |
| Data Privacy | **Microsoft Presidio** (per-source: values for DB/WH, name heuristics for lakes) | `services/privacy_service.py`; `POST /privacy/sources/{id}/scan` | Privacy (PII) page |

## AI Governance

| Stage | Tool | Where (backend) | Frontend |
|-------|------|-----------------|----------|
| Bias & Fairness | **Fairlearn** (MetricFrame, demographic_parity / equalized_odds) | `services/bias_service.py` | Model Detail -> Bias tab |
| Explainability | **SHAP** (global) + **LIME** (local) over a fitted sklearn model | `services/explainability_service.py`; `POST /explainability/explain` | Model Detail -> Explainability tab |
| Model Monitoring | **Evidently AI** (DataDriftPreset report) | `services/monitoring_service.py`; `POST /monitoring/evidently-report` | Monitoring page |
| Drift Detection | **alibi-detect** (KSDrift) | `services/drift_service.py`; `POST /monitoring/drift-check` | Monitoring page |

## Cross-cutting (unchanged)

FastAPI · SQLAlchemy 2.0 async · asyncpg · Alembic · PostgreSQL · JWT (python-jose) ·
bcrypt · Fernet vault · Celery/Redis (optional) · React 18 + TypeScript + Vite + Tailwind +
Zustand + TanStack Query + ECharts.

## Activate the real engines

```bash
cd backend
pip install -r requirements-governance.txt
python -m spacy download en_core_web_sm        # for Presidio
# OpenMetadata: run the OMD server (docker) and set in .env:
#   OPENMETADATA_ENABLED=true
#   OPENMETADATA_URL=http://localhost:8585/api
#   OPENMETADATA_JWT_TOKEN=<bot token>
```

Each endpoint's JSON response includes an `"engine"` field (e.g. `"great_expectations"`,
`"fairlearn"`, `"shap+lime"`, `"evidently"`, `"alibi-detect:KSDrift"`, `"presidio"`) so you
can confirm the real tool is running vs. the fallback.
