"""Model explainability powered by SHAP (global) and LIME (local).

Given labelled tabular records, fits a scikit-learn model and produces:
  - SHAP global feature importance (mean |SHAP value|)
  - LIME local explanation for a chosen instance
Falls back to normalised weight attributions only if shap/lime are unavailable.
"""
from __future__ import annotations

from typing import Dict, List


def shap_available() -> bool:
    try:
        import shap  # noqa: F401
        return True
    except Exception:
        return False


def lime_available() -> bool:
    try:
        import lime  # noqa: F401
        return True
    except Exception:
        return False


def _fit_model(records: List[dict], label_col: str):
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    df = pd.DataFrame(records)
    y = df[label_col]
    X = df.drop(columns=[label_col]).select_dtypes(include=["number"]).fillna(0)
    model = RandomForestClassifier(n_estimators=80, random_state=42)
    model.fit(X, y)
    return model, X, list(X.columns)


def explain(records: List[dict], label_col: str = "label", instance_index: int = 0) -> dict:
    """Return SHAP global importance + LIME local explanation."""
    if not (shap_available() and records):
        return {"engine": "weights", "global_importance": [], "local_explanation": [],
                "note": "shap/lime not installed or no data"}

    import numpy as np
    import shap
    model, X, features = _fit_model(records, label_col)

    # SHAP global importance
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    sv = shap_values[1] if isinstance(shap_values, list) else shap_values
    mean_abs = np.abs(sv).mean(axis=0)
    if mean_abs.ndim > 1:
        mean_abs = mean_abs.mean(axis=1)
    total = float(mean_abs.sum()) or 1.0
    global_importance = sorted(
        [{"feature": f, "importance": round(float(v) / total, 4)} for f, v in zip(features, mean_abs)],
        key=lambda x: x["importance"], reverse=True,
    )

    # LIME local explanation for one instance
    local = []
    if lime_available():
        from lime.lime_tabular import LimeTabularExplainer
        lex = LimeTabularExplainer(X.values, feature_names=features,
                                   class_names=[str(c) for c in model.classes_],
                                   discretize_continuous=True, mode="classification")
        idx = max(0, min(instance_index, len(X) - 1))
        exp = lex.explain_instance(X.values[idx], model.predict_proba, num_features=len(features))
        local = [{"feature": f, "weight": round(w, 4)} for f, w in exp.as_list()]

    return {"engine": "shap+lime", "global_importance": global_importance,
            "local_explanation": local, "instance_index": instance_index}


def feature_importance_from_weights(weights: Dict[str, float]) -> List[dict]:
    total = sum(abs(v) for v in weights.values()) or 1.0
    return sorted(
        [{"feature": k, "importance": round(abs(v) / total, 4),
          "direction": "positive" if v >= 0 else "negative"} for k, v in weights.items()],
        key=lambda x: x["importance"], reverse=True,
    )
