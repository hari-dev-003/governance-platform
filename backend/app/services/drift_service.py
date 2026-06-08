"""Drift detection powered by alibi-detect.

Uses alibi_detect.cd.KSDrift (Kolmogorov-Smirnov two-sample test) to decide whether
a feature's current distribution has drifted from its reference/baseline. Reports the
PSI alongside as a familiar magnitude. Falls back to PSI-only if alibi-detect is missing.
"""
from __future__ import annotations

import math
from typing import List


def _alibi_available() -> bool:
    try:
        import alibi_detect  # noqa: F401
        return True
    except Exception:
        return False


def population_stability_index(baseline: List[float], current: List[float], bins: int = 10) -> float:
    if not baseline or not current:
        return 0.0
    lo, hi = min(baseline), max(baseline)
    if hi == lo:
        return 0.0
    width = (hi - lo) / bins

    def _hist(data):
        counts = [0] * bins
        for x in data:
            idx = 0 if x < lo else (bins - 1 if x >= hi else min(int((x - lo) / width), bins - 1))
            counts[idx] += 1
        n = len(data)
        return [max(c / n, 1e-6) for c in counts]

    pb, pc = _hist(baseline), _hist(current)
    return round(sum((c - b) * math.log(c / b) for b, c in zip(pb, pc)), 4)


def detect_drift(baseline: List[float], current: List[float], p_val: float = 0.05,
                 psi_threshold: float = 0.2) -> dict:
    """Return drift verdict. Engine: alibi-detect KSDrift (with PSI magnitude)."""
    psi = population_stability_index(baseline, current)

    if _alibi_available() and baseline and current:
        import numpy as np
        from alibi_detect.cd import KSDrift
        x_ref = np.array(baseline, dtype=float).reshape(-1, 1)
        x = np.array(current, dtype=float).reshape(-1, 1)
        cd = KSDrift(x_ref, p_val=p_val)
        pred = cd.predict(x, return_p_val=True, return_distance=True)
        is_drift = bool(pred["data"]["is_drift"])
        distance = float(np.array(pred["data"]["distance"]).mean())
        pv = float(np.array(pred["data"]["p_val"]).mean())
        severity = None
        if is_drift:
            severity = "critical" if distance >= 0.5 or psi >= 0.25 else "warning"
        return {"drift": is_drift, "severity": severity, "engine": "alibi-detect:KSDrift",
                "ks_distance": round(distance, 4), "p_value": round(pv, 4), "psi": psi}

    # Fallback: PSI thresholding
    drift = psi >= psi_threshold
    return {"drift": drift, "severity": ("critical" if psi >= 0.25 else "warning") if drift else None,
            "engine": "psi", "psi": psi}


def classify_drift(psi: float, threshold: float = 0.2) -> dict:
    drift = psi >= threshold
    return {"drift": drift, "severity": ("critical" if psi >= 0.25 else "warning") if drift else None,
            "psi": psi}
