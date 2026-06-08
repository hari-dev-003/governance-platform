"""Explainability - SHAP (global) + LIME (local). Only engine."""
from __future__ import annotations

from typing import List


def _fit(records: List[dict], label_col: str):
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    df = pd.DataFrame(records)
    y = df[label_col]
    X = df.drop(columns=[label_col]).select_dtypes(include=["number"]).fillna(0)
    model = RandomForestClassifier(n_estimators=80, random_state=42)
    model.fit(X, y)
    return model, X, list(X.columns)


def explain(records: List[dict], label_col: str = "label", instance_index: int = 0) -> dict:
    """SHAP global importance + LIME local explanation over a fitted sklearn model."""
    import numpy as np
    import shap
    from lime.lime_tabular import LimeTabularExplainer

    model, X, features = _fit(records, label_col)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    sv = shap_values[1] if isinstance(shap_values, list) else shap_values
    mean_abs = np.abs(sv).mean(axis=0)
    if getattr(mean_abs, "ndim", 1) > 1:
        mean_abs = mean_abs.mean(axis=1)
    total = float(mean_abs.sum()) or 1.0
    global_importance = sorted(
        [{"feature": f, "importance": round(float(v) / total, 4)} for f, v in zip(features, mean_abs)],
        key=lambda x: x["importance"], reverse=True)

    lex = LimeTabularExplainer(X.values, feature_names=features,
                               class_names=[str(c) for c in model.classes_],
                               discretize_continuous=True, mode="classification")
    idx = max(0, min(instance_index, len(X) - 1))
    exp = lex.explain_instance(X.values[idx], model.predict_proba, num_features=len(features))
    local = [{"feature": f, "weight": round(w, 4)} for f, w in exp.as_list()]

    return {"engine": "shap+lime", "global_importance": global_importance,
            "local_explanation": local, "instance_index": idx}
