# Data + AI Governance Platform

A full-stack, end-to-end **Data Governance + AI Governance** platform implemented from the
architecture blueprint. FastAPI (async) + React (TypeScript) + PostgreSQL.

It lets an organization connect data sources and model registries, automatically discover
and catalog assets, trace lineage, classify sensitive data (PII/PHI/PCI), monitor data
quality, register AI models, run EU-AI-Act risk assessments, test for bias, explain
predictions, detect model drift, track regulatory compliance, and audit every action.

---

## 1. Architecture

```
PRESENTATION   React 18 + TypeScript + Vite + Tailwind
               React Query | Zustand | React Flow | ECharts
APPLICATION    FastAPI (async)  |  Celery workers (optional)
DOMAIN         Data Gov + AI Gov services
               Auth | Catalog | Lineage | Quality | Audit
INFRASTRUCTURE PostgreSQL 15/16  |  (Redis optional)
                      |
   CONNECTOR PLUGIN SYSTEM (one interface, 13 connectors)
   Databases | Lakes | Warehouses | ETL | Model Registries | IAM
```

### Tech stack (as specified in the blueprint)

| Layer | Tools |
|-------|-------|
| API | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), asyncpg, Alembic |
| Auth | python-jose (JWT), bcrypt, cryptography (Fernet credential vault) |
| Background jobs | Celery + Redis *(optional - see note)* |
| Lineage parsing | sqlglot |
| Data Quality | Great Expectations |
| Data Privacy / PII | Microsoft Presidio |
| Cataloging | OpenMetadata (REST API) |
| Bias & Fairness | Fairlearn |
| Explainability | SHAP + LIME |
| Model Monitoring | Evidently AI |
| Drift Detection | alibi-detect |
| Frontend | React 18 + TypeScript, Vite, Zustand, TanStack Query, React Flow, ECharts, Tailwind |
| Database | PostgreSQL |

---

## 2. Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL 15/16** - e.g. your Docker container in WSL, reachable on `localhost:5432`.

The backend reads DB settings from `backend/.env`. Defaults match a database named
`datagov` with user `user` / password `admin123`. Adjust if yours differ:

```dotenv
DB_USER=user
DB_PASSWORD=admin123
DB_HOST=localhost
DB_PORT=5432
DB_NAME=datagov
```

If you do not yet have the database, create it:

```bash
# inside your WSL Postgres container
psql -U postgres -c "CREATE DATABASE datagov OWNER \"user\";"
```

> **Redis is not required.** Crawls and scans run as FastAPI background tasks. Celery +
> Redis are wired and ready for horizontal scale, but the platform runs fully without them.

---

## 3. Run the backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create a credential-vault encryption key and put it in backend/.env:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   -> set CREDENTIAL_ENCRYPTION_KEY=<that value> in backend/.env

# Apply the database schema
alembic upgrade head

# Start the API
uvicorn app.main:app --reload --port 8000
```

- API docs (Swagger): **http://localhost:8000/docs**
- On first start the app seeds a default organization, an **admin** user, the system
  classification rules, and the compliance frameworks (GDPR, DPDPA, EU AI Act, PCI-DSS).

**Default login:** `admin@local` / `admin123`

> The specific governance engines (Great Expectations, Presidio, Fairlearn, SHAP, LIME,
> Evidently, alibi-detect) live in `requirements-governance.txt`:
>
> ```bash
> pip install -r requirements-governance.txt
> python -m spacy download en_core_web_sm     # Presidio NLP
> ```
> They are lazy-loaded; each endpoint reports which `engine` ran. See `TOOLS_BY_STAGE.md`.
> Cloud connector SDKs (S3, BigQuery, MLflow, ...) are in `requirements-optional.txt`.

## 4. Run the frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api to the backend)
```

Open **http://localhost:5173** and sign in.

### Optional: Celery worker (only if you set up Redis)

```bash
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat   --loglevel=info     # scheduled crawls/quality/drift
```

---

## 5. End-to-end walkthrough

1. **Sources** - add a PostgreSQL connection -> Test -> Scan. Assets are discovered into the
   catalog (schemas -> tables -> columns).
2. **Catalog** - search/filter assets; open one to edit business metadata and run quality.
3. **Classification** - scan a source's columns -> PII/PHI/PCI detected, sensitivity assigned.
4. **Lineage** - view the org-wide source->target graph (richest with a GitHub ETL source).
5. **Glossary** - create a term -> submit -> approve.
6. **AI Model Registry** - register a model -> open it -> Risk Assessment (EU AI Act) ->
   Bias & Fairness test -> Explainability.
7. **Monitoring** - drift alerts (PSI) from model versions.
8. **Compliance** - browse GDPR / DPDPA / EU AI Act / PCI-DSS requirements.
9. **Audit** - every action above is recorded immutably.

---

## 6. Project structure

```
backend/
  app/
    core/         config, async db, JWT security, celery app
    models/       SQLAlchemy ORM (24 tables, exact blueprint schema)
    connectors/   base + registry + Fernet vault + 13 connectors
    services/     catalog, crawl, lineage, classification, quality,
                  ai_governance (EU AI Act risk), bias, drift,
                  explainability, compliance, dashboard, audit, bootstrap
    api/v1/       17 routers
    workers/      Celery tasks (crawler, quality, monitoring, bias)
  alembic/        migrations (initial schema)
frontend/
  src/
    lib/api.ts    typed client for every endpoint
    store/        Zustand auth store
    components/   Layout, UI kit, ECharts + React Flow wrappers
    pages/        16 pages across Dashboard / Data Gov / AI Gov / Compliance
```

---

## 7. Notes on implementation choices

1. **Real engines, lazy-loaded.** The named tools (Great Expectations, Presidio, Fairlearn,
   SHAP, LIME, Evidently, alibi-detect, OpenMetadata) are integrated via their real APIs and
   imported only when used, so the core app boots without them. Install
   `requirements-governance.txt` to activate; each response reports the `engine` used.
2. **Graceful fallback.** If a governance library is not installed, the same endpoint still
   works via a built-in implementation (reported as `engine: builtin`) - so nothing breaks
   before you install the full stack.
3. **`create_all` on startup** is a dev convenience layered on top of the Alembic migration
   (production path is `alembic upgrade head`).
4. **Redis/Celery optional** - background work runs via FastAPI background tasks by default.

---

## 8. Coverage against the blueprint

See `IMPLEMENTATION_COVERAGE.md` for a feature-by-feature checklist of the Data Governance
and AI Governance scope.
