"""Model monitoring - Evidently AI (only engine).

Builds an Evidently DataDriftPreset report from reference vs current datasets and
returns a compact, UI-friendly summary.
"""
from __future__ import annotations

from typing import List


def data_drift_report(reference: List[dict], current: List[dict]) -> dict:
    """Engine: Evidently AI (DataDriftPreset)."""
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
    table = next((m for m in result.get("metrics", []) if m.get("metric") == "DataDriftTable"), None)
    columns = (table or {}).get("result", {}).get("drift_by_columns", {})
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
