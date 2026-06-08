# Step-by-Step Setup (Fresh Machine)

This runs the platform on **Windows** with your **PostgreSQL in Docker (WSL)**.
You'll open **two terminals**: one for the backend (API), one for the frontend (UI).

Project location used below:
`F:\DAI\data-governance-platform\governance-platform`

---

## STEP 0 — Install the prerequisites (once)

Install these if you don't have them:

1. **Python 3.11 or newer** - https://www.python.org/downloads/
   (During install, tick **"Add Python to PATH"**.)
2. **uv** (Python package manager) - in **PowerShell**:
   ```powershell
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Close and reopen PowerShell afterwards so `uv` is on PATH.
3. **Node.js 18 or newer** - https://nodejs.org/ (LTS).
4. **PostgreSQL** - you already run it in Docker under WSL.

Verify everything (open **PowerShell**):

```powershell
python --version      # e.g. Python 3.12.x
uv --version          # e.g. uv 0.5.x
node --version        # e.g. v20.x
npm --version         # e.g. 10.x
```

If `python` opens the Microsoft Store instead, use `py --version` and replace
`python` with `py` in the commands below.

---

## STEP 1 — Make sure the database exists

The app connects to a database named **datagov** with user **user** / password **admin123**
(defined in `backend/.env`).

Check your Postgres container is running (in **WSL** or PowerShell):

```bash
docker ps
```

Find the Postgres container's NAME, then create the database + user if they don't exist
(replace `my_postgres` with your container name):

```bash
docker exec -it my_postgres psql -U postgres -c "CREATE ROLE \"user\" LOGIN PASSWORD 'admin123';"
docker exec -it my_postgres psql -U postgres -c "CREATE DATABASE datagov OWNER \"user\";"
```

If those already exist you'll get a "already exists" notice - that's fine, continue.

Confirm port 5432 is reachable from Windows (Docker Desktop usually forwards it):

```powershell
Test-NetConnection localhost -Port 5432    # TcpTestSucceeded : True
```

> If your DB uses different credentials, edit `backend\.env` (STEP 2.3) to match.

---

## STEP 2 — Backend (API)  — Terminal 1

### 2.1  Go to the backend folder
```powershell
cd F:\DAI\data-governance-platform\governance-platform\backend
```

### 2.2  Install dependencies with uv
```powershell
uv sync
```
This automatically creates a `.venv` and installs every core dependency from
`pyproject.toml` (and writes a `uv.lock`). You do **not** need to activate the venv -
just prefix commands with `uv run`.

### 2.4  Configure the `.env` file
A `.env` already exists. Open it and set a credential-vault key.
Generate one:
```powershell
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copy the printed value into `backend\.env` on this line:
```
CREDENTIAL_ENCRYPTION_KEY=<paste the generated value here>
```
Also confirm the DB lines in `.env` match your Postgres (defaults shown):
```
DB_USER=user
DB_PASSWORD=admin123
DB_HOST=localhost
DB_PORT=5432
DB_NAME=datagov
```

### 2.5  Create the database tables (migration)
```powershell
uv run alembic upgrade head
```
This creates all 24 tables. (Run it again any time with no harm.)

### 2.6  Start the API
```powershell
uv run uvicorn app.main:app --reload --port 8000
```
On first start it seeds the admin user + rules + compliance frameworks.

**Verify:** open http://localhost:8000/docs - you should see the Swagger API.
Leave this terminal running.

---

## STEP 3 — Frontend (UI)  — Terminal 2 (new window)

### 3.1  Go to the frontend folder
```powershell
cd F:\DAI\data-governance-platform\governance-platform\frontend
```

### 3.2  Install dependencies (first time only, ~1-2 min)
```powershell
npm install
```

### 3.3  Start the UI
```powershell
npm run dev
```

**Verify:** open http://localhost:5173

**Log in:**  email `admin@local`  ·  password `admin123`

---

## STEP 4 — First run (try it)

1. **Sources** -> **+ Add Source** -> choose `postgresql` (or `mysql`), fill host=`localhost`, port=`5432`,
   database=`datagov`, username=`user`, password=`admin123` -> **Save**.
2. Click **Test** (should say connected), then **Scan** (discovers the tables).
3. **Catalog** -> see discovered assets; open one, edit metadata, run quality.
4. **Privacy (PII)** -> Scan a source. **Classification** -> Scan. **Lineage** -> view graph.
5. **AI Model Registry** -> Register a model -> open it -> Risk / Bias / Explainability tabs.
6. **Compliance**, **Audit** -> review.

---

## STEP 5 — Presidio language model (required once)

The governance engines (Great Expectations, Presidio, Fairlearn, SHAP, LIME, Evidently,
alibi-detect) are installed automatically by `uv sync` in STEP 2.2. Presidio additionally
needs a small spaCy model - run this once in **Terminal 1**:

```powershell
uv run python -m spacy download en_core_web_sm
```

Every governance API response includes an `"engine"` field (e.g. `great_expectations`,
`presidio`, `fairlearn`, `shap+lime`, `evidently`, `alibi-detect:KSDrift`) confirming the
real tool ran. See `TOOLS_BY_STAGE.md`.

> Optional extras (not needed to run): `uv sync --extra workers` (Celery/Redis),
> `uv sync --extra connectors` (cloud-connector SDKs + ODBC + parquet).


---

## Daily start (after first setup)

**Terminal 1:**
```powershell
cd F:\DAI\data-governance-platform\governance-platform\backend
uv run uvicorn app.main:app --reload --port 8000
```
**Terminal 2:**
```powershell
cd F:\DAI\data-governance-platform\governance-platform\frontend
npm run dev
```
Open http://localhost:5173.

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `uvicorn` says DB not reachable | Postgres container not running, or wrong creds in `.env`. Check `docker ps` and STEP 1. |
| `alembic`/`uvicorn` not found | Prefix with `uv run` (e.g. `uv run alembic upgrade head`), or run `uv sync` first. |
| Login fails | Make sure the API started without errors (it seeds `admin@local`/`admin123` on first boot). |
| UI loads but calls fail / CORS | Backend must be running on port 8000; the UI proxies `/api` to it. |
| `npm run dev` errors | Delete `frontend\node_modules` and run `npm install` again (need Node 18+). |
| `uv` not recognized | Reopen PowerShell after installing uv, or restart your machine so PATH updates. |
| Want to reset all data | `uv run alembic downgrade base` then `uv run alembic upgrade head`. |
| `python` opens Microsoft Store | Use `py` instead of `python`. |

---

## What runs where

| Service | URL | Terminal |
|--------|-----|----------|
| Backend API + Swagger | http://localhost:8000 (`/docs`) | Terminal 1 |
| Frontend UI | http://localhost:5173 | Terminal 2 |
| PostgreSQL | localhost:5432 (your Docker/WSL) | (already running) |
