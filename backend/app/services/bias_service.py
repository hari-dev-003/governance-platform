"""Bias & fairness testing powered by Fairlearn.

Computes group-fairness metrics with fairlearn.metrics (MetricFrame +
demographic_parity_difference / equalized_odds_difference). Falls back to a
built-in numpy implementation only if fairlearn is unavailable.
"""
from __future__ import annotations

from typing import List


def _fairlearn_available() -> bool:
    try:
        import fairlearn  # noqa: F401
        return True
    except Exception:
        return False


def _to_binary(value, positive_label) -> int:
    return 1 if str(value) == str(positive_label) else 0


def compute_group_metrics(records: List[dict], protected_attr: str, label_col: str,
                          pred_col: str, positive_label="1") -> dict:
    """records: [{protected_attr, label, prediction}, ...] -> fairness report."""
    sf = [str(r.get(protected_attr)) for r in records]
    y_true = [_to_binary(r.get(label_col), positive_label) for r in records]
    y_pred = [_to_binary(r.get(pred_col), positive_label) for r in records]

    if _fairlearn_available():
        return _fairlearn_metrics(y_true, y_pred, sf, protected_attr)
    return _builtin_metrics(records, protected_attr, label_col, pred_col, positive_label)


def _fairlearn_metrics(y_true, y_pred, sf, protected_attr) -> dict:
    import numpy as np
    from fairlearn.metrics import (
        MetricFrame, selection_rate, true_positive_rate,
        demographic_parity_difference, equalized_odds_difference,
    )
    y_true = np.array(y_true); y_pred = np.array(y_pred); sf = np.array(sf)
    mf = MetricFrame(
        metrics={"selection_rate": selection_rate, "true_positive_rate": true_positive_rate},
        y_true=y_true, y_pred=y_pred, sensitive_features=sf,
    )
    by_group = mf.by_group
    demographic_parity = {g: round(float(by_group.loc[g, "selection_rate"]), 4) for g in by_group.index}
    equal_opportunity = {g: round(float(by_group.loc[g, "true_positive_rate"]), 4) for g in by_group.index}
    dp_gap = round(float(demographic_parity_difference(y_true, y_pred, sensitive_features=sf)), 4)
    eo_gap = round(float(equalized_odds_difference(y_true, y_pred, sensitive_features=sf)), 4)

    # predictive parity (precision per group)
    predictive_parity = {}
    for g in set(sf):
        mask = sf == g
        pp_den = int((y_pred[mask] == 1).sum())
        pp_num = int(((y_pred[mask] == 1) & (y_true[mask] == 1)).sum())
        predictive_parity[g] = round(pp_num / pp_den, 4) if pp_den else 0.0

    verdict = "pass"
    if dp_gap > 0.2 or eo_gap > 0.2:
        verdict = "fail"
    elif dp_gap > 0.1 or eo_gap > 0.1:
        verdict = "warning"

    return {"protected_attribute": protected_attr, "demographic_parity": demographic_parity,
            "equal_opportunity": equal_opportunity, "predictive_parity": predictive_parity,
            "demographic_parity_gap": dp_gap, "equal_opportunity_gap": eo_gap,
            "verdict": verdict, "groups": sorted(set(sf)), "engine": "fairlearn"}


def _builtin_metrics(records, protected_attr, label_col, pred_col, positive_label) -> dict:
    pos = str(positive_label)
    groups: dict[str, dict] = {}
    for r in records:
        g = str(r.get(protected_attr))
        groups.setdefault(g, {"pp": [], "tn": 0, "td": 0, "pn": 0, "pd": 0})
        pp = 1 if str(r.get(pred_col)) == pos else 0
        lp = 1 if str(r.get(label_col)) == pos else 0
        groups[g]["pp"].append(pp)
        if lp:
            groups[g]["td"] += 1; groups[g]["tn"] += pp
        if pp:
            groups[g]["pd"] += 1; groups[g]["pn"] += lp
    dp = {g: round(sum(v["pp"]) / len(v["pp"]), 4) if v["pp"] else 0.0 for g, v in groups.items()}
    eo = {g: round(v["tn"] / v["td"], 4) if v["td"] else 0.0 for g, v in groups.items()}
    pp = {g: round(v["pn"] / v["pd"], 4) if v["pd"] else 0.0 for g, v in groups.items()}
    gap = lambda d: round(max(d.values()) - min(d.values()), 4) if d else 0.0
    dpg, eog = gap(dp), gap(eo)
    verdict = "fail" if (dpg > 0.2 or eog > 0.2) else "warning" if (dpg > 0.1 or eog > 0.1) else "pass"
    return {"protected_attribute": protected_attr, "demographic_parity": dp, "equal_opportunity": eo,
            "predictive_parity": pp, "demographic_parity_gap": dpg, "equal_opportunity_gap": eog,
            "verdict": verdict, "groups": sorted(groups), "engine": "builtin"}
