# Connect SageMaker & Data, and Test AI Governance (Beginner Guide)

This guide takes you from a **connected SageMaker account** all the way through **fetching
models**, then running **Risk Assessment, Bias & Fairness, Explainability, and Drift
Detection** on them. It assumes you've already done `SAGEMAKER_MODEL_DEPLOYMENT.md` and have:

- An AWS **Access key ID**, **Secret access key**, and **Region** (e.g. `us-east-1`).
- A model in the SageMaker Model Registry (group `credit-risk-models`).

If you don't have SageMaker, you can still test everything: see **"No SageMaker? Register a
model by hand"** at the bottom.

---

## 0. Before you start — make sure the platform is running

1. **Backend** (the brain). In a terminal:
   ```
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   Leave it running. It serves the API at **http://localhost:8000**.
2. **Frontend** (the website). In a second terminal:
   ```
   cd frontend
   npm install      # first time only
   npm run dev
   ```
   Open **http://localhost:5173** in your browser.
3. **Log in** with the default admin account:
   - Email: `admin@local`
   - Password: `admin123`

4. **Install the AWS library** (once) so SageMaker can be contacted. In the backend's
   virtual environment:
   ```
   cd backend
   uv pip install boto3
   ```
   (It's already listed as a dependency; this just makes sure it's installed.)

> Throughout this guide, anything you do on the **website** is the easy path. A few advanced
> "real data" tests use **API commands** (copy‑paste). Both are explained.

---

## 1. Connect SageMaker as a source

1. In the website, open the **Sources** (or **Data Sources**) page.
2. Click **+ Add Source**.
3. Fill in:
   - **Connection name**: `My SageMaker`
   - **Type**: select **`sagemaker (model_registry)`** from the dropdown.
   - The form now shows the right fields (a small help line appears under them):
     - **aws access key id** → paste your `AKIA...` key
     - **aws secret access key** → paste your secret (it shows as dots — that's correct)
     - **region** → e.g. `us-east-1`
4. Click **Save Connection**.
5. On the new row, click **Test**. You should see **"Connected to SageMaker"**. If not, see
   Troubleshooting at the end.
6. Click **Scan**. This fetches your model groups and versions from SageMaker into the
   catalog. Wait a few seconds and refresh.

> **What just happened:** the platform read your SageMaker Model Registry and stored each
> model group and version as catalogue items.

---

## 2. Bring the models into the AI Model Registry

1. Open the **AI Model Registry** page (often called **Models**).
2. At the top, find the **registry source** dropdown, choose **My SageMaker**, and click
   **Sync from registry**.
3. You'll see a message like **"Synced 1 model(s) and 1 version(s)"** and your model
   `credit-risk-models` now appears in the table with a **Risk Tier** of *unclassified*.
4. Click the model name to open its **detail page** — you'll see its **Versions** and tabs
   for **Risk Assessment**, **Bias & Fairness**, and **Explainability**.

✅ Your SageMaker model is now under governance.

---

## 3. Risk Assessment (no data needed — start here)

1. On the model's detail page, click the **Risk Assessment** tab.
2. You'll see the **EU AI Act questionnaire** (yes/no checkboxes). Tick the ones that apply.
   For a credit model, tick **"Determines access to essential services / credit?"**.
3. Click **Assess Risk**.
4. The result shows a **Risk Tier** (e.g. *high*), the **EU AI Act category**, and a list of
   **required actions**. The model's tier updates everywhere.
5. You can **Download model card (PDF)** from the button at the top of the page — it includes
   this assessment.

---

## 4. Prepare a sample dataset (needed for Bias, Explainability, Drift)

Bias, explainability, and drift need **data with outcomes** — specifically rows that include
the model's **prediction**, the **true label**, a **protected attribute** (like gender), and
some **numeric features**. SageMaker's registry stores the *model*, not this data, so we
create a small table in your own PostgreSQL database and connect it.

### 4a. Create the sample table

Open your PostgreSQL (the same one the platform uses, or any Postgres you can reach) and run
this SQL. It makes a realistic 200‑row predictions table:

```sql
CREATE TABLE IF NOT EXISTS public.model_predictions (
    id              SERIAL PRIMARY KEY,
    gender          TEXT,          -- protected attribute (M / F)
    income          NUMERIC,
    age             INTEGER,
    debt            NUMERIC,
    credit_history  NUMERIC,
    label           INTEGER,       -- the TRUE outcome (1 = good, 0 = bad)
    prediction      INTEGER        -- what the model PREDICTED (1 / 0)
);

INSERT INTO public.model_predictions (gender, income, age, debt, credit_history, label, prediction)
SELECT
    CASE WHEN random() < 0.5 THEN 'M' ELSE 'F' END,
    round((30 + random()*90)::numeric, 1),
    (20 + (random()*45))::int,
    round((random()*60)::numeric, 1),
    round((random()*100)::numeric, 1),
    (random() < 0.6)::int,
    -- introduce a little bias: model favours 'M' slightly, for demo purposes
    CASE WHEN random() < 0.6 THEN 1 ELSE 0 END
FROM generate_series(1, 200);
```

### 4b. Connect that database to the platform

1. **Sources → + Add Source**.
2. **Type**: `postgresql`. Fill in **host, port, database, username, password** for your
   Postgres (for the platform's own DB running in Docker/WSL this is usually host
   `localhost`, port `5432`, database `datagov`, user/password as configured).
3. **Save**, then **Test**, then **Scan**.
4. Open the **Catalog** page — you should now see the table **`model_predictions`** with its
   columns (gender, income, label, prediction, …).

### 4c. Find the table's ID (you'll need it for the API tests)

Two easy ways:
- **Website:** click `model_predictions` in the Catalog. The web address becomes
  `…/assets/XXXXXXXX-XXXX-…` — that long code **after `/assets/`** is the **dataset ID**.
- **API:** see section 8 (it lists tables with their IDs).

---

## 5. Bias & Fairness (Fairlearn)

### Easiest test (1 click, built‑in demo data)
1. On the model detail page → **Bias & Fairness** tab → **Run Bias Test**.
2. You'll get a **verdict** (pass / warning / fail) and a chart comparing **Demographic
   Parity** and **Equal Opportunity** between groups. You can **Download report (PDF)**.

> This uses a small built‑in sample so you can see it work instantly.

### Real test on your dataset (uses the table from step 4)
This uses an API command because it points at your real data. First get a login token, then
run the bias test against your `model_predictions` table.

```bash
# 1) Get a token (default admin login)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin@local&password=admin123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2) Run the bias test. Replace DATASET_ID and VERSION_ID (see sections 4c and 8).
curl -s -X POST http://localhost:8000/api/v1/bias-tests \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
        "model_version_id": "VERSION_ID",
        "test_dataset_id":  "DATASET_ID",
        "protected_attribute": "gender",
        "label_column": "label",
        "prediction_column": "prediction",
        "positive_label": "1"
      }'
```

The response includes per‑group **demographic_parity**, **equal_opportunity**,
**predictive_parity**, and an overall **verdict**. (On Windows PowerShell, use `curl.exe`
and put the JSON on one line, or use the built‑in demo button instead.)

> **Engine:** Fairlearn. **Required columns:** the protected attribute (`gender`), the true
> `label`, and the model's `prediction`. If you see *"column not found"*, your table is
> missing one of these names.

---

## 6. Explainability (SHAP + LIME)

### Easiest test (1 click)
1. Model detail page → **Explainability** tab → **Compute SHAP + LIME**.
2. You get a **SHAP global feature‑importance** bar chart (which features matter most) and a
   **LIME local explanation** (why one specific row was predicted the way it was).

### Real test on your dataset
```bash
curl -s -X POST http://localhost:8000/api/v1/explainability/explain \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "dataset_id": "DATASET_ID", "label_col": "label", "instance_index": 0 }'
```
To **save** the importance onto a model version (so it shows on the model later):
```bash
curl -s -X POST http://localhost:8000/api/v1/explainability/versions/VERSION_ID/feature-importance \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "dataset_id": "DATASET_ID", "label_col": "label" }'
```

> **Engine:** SHAP (global) + LIME (local). It trains a quick surrogate model on the numeric
> columns of your dataset and explains it.

---

## 7. Drift Detection & Monitoring (Evidently + alibi‑detect)

Drift = "has the live data drifted away from what the model was trained on?" You compare a
**reference** dataset (baseline) against a **current** dataset.

### Easiest test (1 click)
1. Open the **Monitoring** page.
2. Click **Run Evidently Report** → see which columns drifted (built‑in demo data).
3. Click **Run KS Drift Check** → see a statistical drift verdict (KS distance + PSI).
4. Any drift creates a **Drift Alert** in the table below; click **Ack** to acknowledge it.

### Real test on your data (two datasets)
Make a second table to act as "current/newer" data — e.g. copy `model_predictions` but shift
`income` up to simulate drift:
```sql
CREATE TABLE public.model_predictions_current AS
SELECT id, gender, income + 40 AS income, age, debt, credit_history, label, prediction
FROM public.model_predictions;
```
Scan the source again so the new table is catalogued, get **both table IDs**, then:

```bash
# Single-feature drift (alibi-detect KS test)
curl -s -X POST http://localhost:8000/api/v1/monitoring/drift-check \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "model_version_id":"VERSION_ID", "feature":"income",
        "baseline_dataset_id":"DATASET_ID", "current_dataset_id":"CURRENT_DATASET_ID" }'

# Full-dataset drift report (Evidently)
curl -s -X POST http://localhost:8000/api/v1/monitoring/evidently-report \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "model_version_id":"VERSION_ID",
        "reference_dataset_id":"DATASET_ID", "current_dataset_id":"CURRENT_DATASET_ID" }'
```

### Automated/scheduled monitoring
Create a **monitoring config** that remembers the two datasets, then trigger a sweep (you can
run the sweep on a schedule from your OS task scheduler):
```bash
# create the config
curl -s -X POST http://localhost:8000/api/v1/monitoring/configs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{ "model_version_id":"VERSION_ID",
        "reference_dataset_id":"DATASET_ID", "current_dataset_id":"CURRENT_DATASET_ID" }'

# run all active monitors (raises alerts if drift found)
curl -s -X POST http://localhost:8000/api/v1/monitoring/run-all \
  -H "Authorization: Bearer $TOKEN"
```
New alerts appear on the **Monitoring** page.

---

## 8. Handy: list IDs from the API

```bash
# your connected sources (find the SageMaker source id, postgres source id)
curl -s http://localhost:8000/api/v1/sources -H "Authorization: Bearer $TOKEN"

# tables in the catalog (find DATASET_ID = the model_predictions table's "id")
curl -s "http://localhost:8000/api/v1/assets?type=table&limit=200" -H "Authorization: Bearer $TOKEN"

# your AI models, then versions of one model (find VERSION_ID)
curl -s http://localhost:8000/api/v1/ai-models -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/ai-models/MODEL_ID/versions -H "Authorization: Bearer $TOKEN"
```

---

## 9. The full end‑to‑end flow at a glance

```
Deploy model in SageMaker (other file)
        │
        ▼
Sources → Add SageMaker → Test → Scan         (fetch model groups + versions)
        │
        ▼
AI Model Registry → Sync from registry        (models now governed)
        │
        ├── Risk Assessment  (questionnaire → EU AI Act tier)         ✅ no data needed
        │
   Sources → Add PostgreSQL → Scan  (catalog the model_predictions table)
        │
        ├── Bias & Fairness   (Fairlearn, needs gender/label/prediction)
        ├── Explainability    (SHAP + LIME, needs features + label)
        └── Drift & Monitoring(Evidently + alibi-detect, needs 2 datasets)
        │
        ▼
Download model card / bias / risk PDFs;  approve & promote versions
```

---

## 10. Troubleshooting

- **Test says "boto3 not installed"** → in `backend`, run `uv pip install boto3`, restart the
  backend.
- **Test fails with credentials/region error** → re‑check the Access key ID/secret and that
  the **Region** matches where your model lives (e.g. `us-east-1`).
- **Sync says 0 models** → you must click **Scan** on the SageMaker source *before* Sync, and
  your SageMaker Model Registry must actually contain a model package group (see the
  deployment guide). Endpoints alone aren't models.
- **Bias says "column not found"** → your dataset must have the exact columns `gender`,
  `label`, `prediction`. Re‑check the table and re‑Scan.
- **Privacy/PII scan errors about `en_core_web_sm`** → that's a different feature; install the
  model: `cd backend && uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl`.
- **Drift/Evidently/Fairlearn errors on Windows** → make sure the backend venv has the ML
  libraries installed (`uv pip install -e .` from `backend`).

---

## No SageMaker? Register a model by hand (so you can still test governance)

1. **AI Model Registry → + Register Model**: name `credit-risk`, type `classification`,
   framework `sklearn`, domain `lending`. Save.
2. Open the model → add a **version** (via the API or the registry sync). For quick testing,
   the **Bias**, **Explainability**, and **Monitoring** demo buttons work on built‑in sample
   data without any version or dataset.
3. Everything else (Risk Assessment, PDFs, alerts) works exactly as above.

This lets you exercise the entire AI‑governance workflow even before wiring up a real cloud
registry.
