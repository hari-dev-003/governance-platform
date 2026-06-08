"""Bias & Fairness - Fairlearn (only engine)."""
from __future__ import annotations

from typing import List


def _bin(value, positive_label) -> int:
    return 1 if str(value) == str(positive_label) else 0


def compute_group_metrics(records: List[dict], protected_attr: str, label_col: str,
                          pred_col: str, positive_label="1") -> dict:
    """Engine: Fairlearn (MetricFrame + demographic_parity / equalized_odds)."""
    import numpy as np
    from fairlearn.metrics import (
        MetricFrame, selection_rate, true_positive_rate,
        demographic_parity_difference, equalized_odds_difference,
    )
    sf = np.array([str(r.get(protected_attr)) for r in records])
    y_true = np.array([_bin(r.get(label_col), positive_label) for r in records])
    y_pred = np.array([_bin(r.get(pred_col), positive_label) for r in records])

    mf = MetricFrame(
        metrics={"selection_rate": selection_rate, "true_positive_rate": true_positive_rate},
        y_true=y_true, y_pred=y_pred, sensitive_features=sf,
    )
    by = mf.by_group
    demographic_parity = {g: round(float(by.loc[g, "selection_rate"]), 4) for g in by.index}
    equal_opportunity = {g: round(float(by.loc[g, "true_positive_rate"]), 4) for g in by.index}
    dp_gap = round(float(demographic_parity_difference(y_true, y_pred, sensitive_features=sf)), 4)
    eo_gap = round(float(equalized_odds_difference(y_true, y_pred, sensitive_features=sf)), 4)

    predictive_parity = {}
    for g in set(sf):
        m = sf == g
        den = int((y_pred[m] == 1).sum())
        num = int(((y_pred[m] == 1) & (y_true[m] == 1)).sum())
        predictive_parity[g] = round(num / den, 4) if den else 0.0

    verdict = "fail" if (dp_gap > 0.2 or eo_gap > 0.2) else "warning" if (dp_gap > 0.1 or eo_gap > 0.1) else "pass"
    return {"protected_attribute": protected_attr, "demographic_parity": demographic_parity,
            "equal_opportunity": equal_opportunity, "predictive_parity": predictive_parity,
            "demographic_parity_gap": dp_gap, "equal_opportunity_gap": eo_gap,
            "verdict": verdict, "groups": sorted(set(sf.tolist())), "engine": "fairlearn"}
