"""Model monitoring powered by Evidently AI.

Builds Evidently reports (Data Drift + Data Quality presets) from a reference and a
current dataset, and returns a compact, UI-friendly summary. Degrades to a simple
column-overlap summary only if evidently is unavailable.
"""
from __future__ import annotations

from typing import List


def evidently_available() -> bool:
    try:
        import evidently  # noqa: F401
        return True
    except Exception:
        return False


def data_drift_report(reference: List[dict], current: List[dict]) -> dict:
    """Engine: Evidently AI DataDriftPreset + DataQualityPreset."""
    if not (evidently_available() and reference and current):
        return {"engine": "unavailable", "dataset_drift": None,
                "note": "evidently not installed or insufficient data"}

    import pandas as pd
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset

    ref_df = pd.DataFrame(reference)
    cur_df = pd.DataFrame(current)
    common = [c for c in ref_df.columns if c in cur_df.columns]
    ref_df, cur_df = ref_df[common], cur_df[common]

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=ref_df, current_data=cur_df)
    result = report.as_dict()

    drift_metric = next((m for m in result.get("metrics", [])
                         if m.get("metric") == "DatasetDriftMetric"), None)
    summary = (drift_metric or {}).get("result", {})
    by_col_metric = next((m for m in result.get("metrics", [])
                          if m.get("metric") == "DataDriftTable"), None)
    columns = (by_col_metric or {}).get("result", {}).get("drift_by_columns", {})
    per_column = [
        {"column": c, "drift_detected": v.get("drift_detected"),
         "drift_score": round(float(v.get("drift_score", 0) or 0), 4),
         "stattest": v.get("stattest_name")}
        for c, v in columns.items()
    ]
    return {"engine": "evidently",
            "dataset_drift": summary.get("dataset_drift"),
            "drifted_columns": summary.get("number_of_drifted_columns"),
            "total_columns": summary.get("number_of_columns"),
            "share_drifted": round(float(summary.get("share_of_drifted_columns", 0) or 0), 4),
            "per_column": per_column}
