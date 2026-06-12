# Deploy Your Own Model in AWS SageMaker (Step‑by‑Step for Beginners)

This guide walks you from **zero** to a **trained model registered in the SageMaker Model
Registry** — which is exactly what the governance platform reads when it connects to
SageMaker. No prior AWS or machine‑learning experience is assumed. Just follow each step.

> **Why register a model?** The governance platform fetches models from SageMaker's
> **Model Registry** (groups of models called *Model Package Groups*, each containing
> versions). So our goal is to put one model there. Deploying a live prediction endpoint
> is optional and shown at the end.

> 💰 **Cost warning.** AWS is mostly free to *sign up*, but training and endpoints cost a
> few US dollars if you leave them running. This whole tutorial costs well under **$2** if
> you follow the cleanup step at the end. Always delete endpoints when done.

---

## Part 1 — Create an AWS account

1. Go to **https://aws.amazon.com/** and click **Create an AWS Account** (top right).
2. Enter your email, choose an account name (e.g. "my-ml-test"), and verify the email.
3. Enter a **credit/debit card** (required even for free tier — you won't be charged unless
   you exceed free limits or leave paid resources running).
4. Choose the **Basic (free) support plan**.
5. Finish and **sign in to the AWS Console** at https://console.aws.amazon.com/.
6. In the **top‑right corner**, pick a **Region** and remember it (e.g. **N. Virginia /
   `us-east-1`**). Use the same region everywhere in this guide.

---

## Part 2 — Create access keys (so the platform can read your models)

The governance platform logs into your AWS account using an **access key**. We'll make a
dedicated user with **read‑only** SageMaker access — safe to paste into the platform.

1. In the AWS Console search bar, type **IAM** and open it.
2. Left menu → **Users** → **Create user**.
3. Name it `governance-readonly` → **Next**.
4. **Permissions** → choose **Attach policies directly** → search and tick
   **`AmazonSageMakerReadOnly`** → **Next** → **Create user**.
5. Click the new user → **Security credentials** tab → **Create access key**.
6. Choose **Application running outside AWS** → **Next** → **Create access key**.
7. **COPY AND SAVE BOTH VALUES NOW** (you can't see the secret again):
   - **Access key ID** → looks like `AKIA...`
   - **Secret access key** → a long random string
8. Keep these two values plus your **Region** (e.g. `us-east-1`). You'll paste them into the
   platform later (see the companion file `SAGEMAKER_PLATFORM_INTEGRATION.md`).

> You also need a key that can *create* models for the training below. The simplest path is
> to do the training inside **SageMaker Studio** (next part), which uses an automatic role —
> no extra keys needed.

---

## Part 3 — Open SageMaker Studio (your cloud notebook)

1. In the AWS Console search bar, type **SageMaker** and open **Amazon SageMaker**.
2. Left menu → **Studio**.
3. If asked to set up a domain, click **Set up for single user (Quick setup)** and wait
   ~5–10 minutes for it to finish (status becomes *InService*).
4. Click **Open Studio**. A web‑based coding environment opens.
5. Inside Studio: **File → New → Notebook**. When asked, pick the
   **Python 3 (Data Science)** kernel and the smallest instance (e.g. `ml.t3.medium`).

---

## Part 4 — Train and register a model (copy‑paste)

Paste the following into a notebook cell and run it (click the cell, press **Shift+Enter**).
It trains a tiny credit‑risk model with SageMaker's built‑in **XGBoost** and registers it
into a **Model Package Group** named `credit-risk-models`.

```python
# --- 1. Setup ---
import sagemaker, boto3, numpy as np, pandas as pd
from sagemaker import image_uris
from sklearn.datasets import make_classification

sess   = sagemaker.Session()
region = sess.boto_region_name
role   = sagemaker.get_execution_role()      # Studio provides this automatically
bucket = sess.default_bucket()               # an S3 bucket SageMaker created for you
prefix = "credit-risk-demo"
print("Region:", region, "| Bucket:", bucket)

# --- 2. Make a small synthetic dataset (label must be the FIRST column for XGBoost) ---
X, y = make_classification(n_samples=1000, n_features=6, n_informative=4, random_state=42)
cols = ["income", "age", "debt", "credit_history", "num_loans", "utilization"]
df = pd.DataFrame(X, columns=cols)
df.insert(0, "label", y)                      # XGBoost wants the target in column 0
train = df.sample(frac=0.8, random_state=1)
valid = df.drop(train.index)
train.to_csv("train.csv", index=False, header=False)
valid.to_csv("valid.csv", index=False, header=False)

train_s3 = sess.upload_data("train.csv", bucket=bucket, key_prefix=f"{prefix}/train")
valid_s3 = sess.upload_data("valid.csv", bucket=bucket, key_prefix=f"{prefix}/valid")

# --- 3. Train with built-in XGBoost ---
xgb_image = image_uris.retrieve("xgboost", region, version="1.7-1")
estimator = sagemaker.estimator.Estimator(
    image_uri=xgb_image, role=role,
    instance_count=1, instance_type="ml.m5.large",
    output_path=f"s3://{bucket}/{prefix}/output", sagemaker_session=sess,
)
estimator.set_hyperparameters(objective="binary:logistic", num_round=50, max_depth=4)
from sagemaker.inputs import TrainingInput
estimator.fit({
    "train":      TrainingInput(train_s3, content_type="text/csv"),
    "validation": TrainingInput(valid_s3, content_type="text/csv"),
})

# --- 4. Register the trained model into the Model Registry ---
model_package_group = "credit-risk-models"
estimator.register(
    content_types=["text/csv"], response_types=["text/csv"],
    inference_instances=["ml.t2.medium"], transform_instances=["ml.m5.large"],
    model_package_group_name=model_package_group,
    approval_status="Approved",
    description="Demo credit-risk XGBoost model for AI governance testing",
)
print("✅ Registered model into group:", model_package_group)
```

When it finishes you'll see **"✅ Registered model into group: credit-risk-models"**.
Training takes ~3–5 minutes.

> Want a second version? Re‑run the **train** and **register** cells — it adds *version 2*
> to the same group. The platform will show both versions.

---

## Part 5 — Confirm it's in the Model Registry

1. Back in the AWS Console → **SageMaker** → left menu → **Models → Model registry**
   (or "Model Package Groups").
2. You should see **`credit-risk-models`** with one (or more) versions, status **Approved**.

That's the exact thing the governance platform will fetch. ✅ **You're done with the
required part.** Continue to `SAGEMAKER_PLATFORM_INTEGRATION.md` to connect it.

---

## Part 6 (Optional) — Deploy a live prediction endpoint

Only do this if you want a real‑time API. **It costs money while running — delete it after.**

```python
predictor = estimator.deploy(
    initial_instance_count=1, instance_type="ml.t2.medium",
    endpoint_name="credit-risk-endpoint",
)
# quick test
import io
sample = "0.1,0.2,0.3,0.4,0.5,0.6"   # 6 feature values (no label)
print(predictor.predict(sample, initial_args={"ContentType": "text/csv"}))
```

The endpoint also appears in the platform (as a *deployment*).

---

## Part 7 — Clean up to avoid charges (IMPORTANT)

1. **Delete the endpoint** (if you created one):
   ```python
   predictor.delete_endpoint()
   ```
   Or in the console: **SageMaker → Inference → Endpoints → select → Delete**.
2. **Stop Studio apps**: SageMaker → **Studio → Running instances** → stop them.
3. Registered models and the model group cost **nothing** to keep — leave them so the
   platform can read them.
4. (Optional) Empty the S3 bucket the demo created if you want zero storage cost.

---

## What you now have

- An IAM **Access key ID + Secret access key** (read‑only) and your **Region**.
- A **Model Package Group** `credit-risk-models` with at least one approved version in the
  SageMaker Model Registry.

➡️ **Next:** open `SAGEMAKER_PLATFORM_INTEGRATION.md` to connect SageMaker to the
governance platform and run risk, bias, explainability, and drift checks.
