# Data Governance - Full Setup & Test Guide (Postgres)

Goal: stand the platform up and exercise **every Data Governance feature** end-to-end using
only Postgres + a seeded sample database. Follow top to bottom.

Paths assume the project at `E:\Demo-flyy-hands-on\governance-platform`.

---

## Part A - Prerequisites
- **uv** (`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`), **Node 18+**, and your
  **PostgreSQL in Docker/WSL** running on `localhost:5432`.
- The platform's own metadata DB is **datagov** (user `user` / password `admin123`, per `backend\.env`).

---

## Part B - Start the platform

**Terminal 1 - backend**
```powershell
cd E:\Demo-flyy-hands-on\governance-platform\backend
uv sync                                            # installs everything (already done for you)
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl     # Presidio model (one time)
# put a vault key in backend\.env if not already set:
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   -> CREDENTIAL_ENCRYPTION_KEY=<paste> in backend\.env
uv run alembic upgrade head                         # create the 24 governance tables in datagov
uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - frontend**
```powershell
cd E:\Demo-flyy-hands-on\governance-platform\frontend
npm install
npm run dev
```
Open http://localhost:5173 -> log in **admin@local / admin123**.

---

## Part C - Create the sample business database

This is the data you'll *govern* (kept separate from `datagov`). Find your Postgres
container name with `docker ps`, then (PowerShell, replace `my_pg`):

```powershell
# 1. create an empty database
docker exec -i my_pg psql -U user -c "CREATE DATABASE sample_shop;"

# 2. load the seed (PII columns, foreign keys, deliberate quality issues)
Get-Content backend\scripts\sample_data.sql | docker exec -i my_pg psql -U user -d sample_shop
```
(If you have `psql` on Windows instead: `psql -h localhost -U user -d sample_shop -f backend\scripts\sample_data.sql`)

You should see row counts: customers 200, products 50, orders 600, order_items 1500, payments 400.

**What's in it (and why):**
- `customers` - email, phone, ssn, ip_address, names -> **Privacy (Presidio)** + **Classification**
- `payments.card_number` (Visa test number) -> **PCI** detection
- foreign keys (orders->customers, order_items->orders/products, payments->orders) -> **Lineage**
- seeded issues: null emails, duplicate emails, negative `total_amount`, null `status` -> **Quality** failures

---

## Part D - Run the Data Governance workflow (in the UI)

### 1. Connect the source
**Sources -> + Add Source**: type `postgresql`, host `localhost`, port `5432`,
database **`sample_shop`**, username `user`, password `admin123` -> **Save**.
Click **Test** (expect "Connected"), then **Scan**.

### 2. Catalog  (Catalog page)
Expect **5 tables** + their columns discovered. Open `customers` to see columns and edit
business metadata (description, domain, sensitivity).

### 3. Lineage  (Lineage page)
The scan derived lineage from foreign keys. Expect edges:
`customers -> orders -> order_items`, `products -> order_items`, `orders -> payments`.

### 4. Classification  (Classification page)
Click **Scan columns** on the sample_shop source. Expect detections (system rules) on
columns named email/ssn/card/first_name/last_name -> categories PII / PCI / PHI / Financial,
and sensitivity raised on those columns.

### 5. Privacy - Presidio  (Privacy (PII) page)
Click **Scan PII** on the sample_shop source. Strategy = `presidio_values` (it samples real
values). Expect findings: **EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, IP_ADDRESS, CREDIT_CARD**.
The `engine` shows `presidio`.

### 6. Data Quality - Great Expectations
The simplified UI runs rules but has no rule-builder form, so create + run rules with the helper:
```powershell
# Terminal 3 (or stop nothing - it uses its own DB session)
cd E:\Demo-flyy-hands-on\governance-platform\backend
uv run python scripts/add_quality_rules.py
```
Expect output like:
```
customers: engine=great_expectations score=0.0 passed=0 failed=2   (null + duplicate emails)
orders:    engine=great_expectations score=0.0 passed=0 failed=2   (negative totals + null status)
```
Then refresh the **Quality** page / open the table in **Catalog** to see the scores.

### 7. Glossary / Policies / Access / Audit  (UI)
- **Glossary**: create a term ("Customer") -> Submit -> Approve.
- **Policies**: add an access/retention policy.
- **Access Requests**: create one, then Approve/Reject.
- **Audit**: every action above appears here (immutable trail).

---

## Part E - One-command full check (optional)

To verify all of the above (plus the AI side) programmatically against your Postgres:
```powershell
cd E:\Demo-flyy-hands-on\governance-platform\backend
uv run python scripts/acceptance_test.py
```
It prints PASS + the engine used for each stage and ends with
`Fully operational end-to-end` when everything is green.

---

## Data Governance acceptance checklist

| # | Feature | How to confirm | Expected |
|---|---------|----------------|----------|
| 1 | Connect (native RDBMS) | Sources -> Test | "Connected" |
| 2 | Catalog | Scan -> Catalog | 5 tables + columns |
| 3 | Lineage | Lineage page | FK-derived edges |
| 4 | Classification | Classification -> Scan | PII/PCI/PHI/Financial hits |
| 5 | Privacy (Presidio) | Privacy -> Scan PII | email/phone/ssn/ip/card findings, engine=presidio |
| 6 | Quality (Great Expectations) | add_quality_rules.py | failures on seeded issues, engine=great_expectations |
| 7 | Glossary workflow | draft->submit->approve | status changes |
| 8 | Policies | create policy | listed |
| 9 | Access requests | create + review | approved/rejected |
| 10 | Audit trail | Audit page | every action logged |
