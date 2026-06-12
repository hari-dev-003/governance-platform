"""Deletion of a data source and everything derived from it.

The schema wires most child rows to their parents with ``ON DELETE CASCADE``,
but a handful of foreign keys are intentionally *not* cascading (they reference
assets/model-versions that may be shared or audited):

  * ``ai_models.source_id``              -> data_sources   (no cascade)
  * ``classification_runs.source_id``    -> data_sources   (no cascade)
  * ``lineage_edges.transformation_asset_id`` -> assets    (no cascade)
  * ``bias_test_runs.test_dataset_id``   -> assets         (no cascade)
  * ``compliance_mappings.asset_id``     -> assets         (no cascade)
  * ``drift_alerts.model_version_id`` / ``.monitoring_config_id`` (no cascade)

A naive ``DELETE FROM data_sources`` therefore fails with a ForeignKey
violation as soon as the source has been crawled. This module removes the
dependent rows in FK-safe order inside the caller's transaction, so the final
source delete always succeeds and leaves no orphans behind.
"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_models import AIModel, AIModelVersion
from app.models.assets import Asset
from app.models.bias import BiasTestRun
from app.models.classification import ClassificationResult, ClassificationRun
from app.models.compliance import ComplianceMapping
from app.models.lineage import LineageEdge
from app.models.monitoring import MonitoringConfig
from app.models.monitoring import DriftAlert
from app.models.sources import DataSource


async def delete_source_cascade(db: AsyncSession, source: DataSource) -> dict[str, int]:
    """Delete ``source`` and every row that depends on it.

    Runs inside the caller's transaction (no commit here). Returns a small
    summary of how many rows were removed per category, for the audit log.
    """
    sid = source.id

    # Sub-selects evaluated lazily by each DELETE; valid until the rows they
    # reference are themselves deleted, so order matters (assets last).
    asset_ids = select(Asset.id).where(Asset.source_id == sid)
    model_ids = select(AIModel.id).where(AIModel.source_id == sid)
    version_ids = select(AIModelVersion.id).where(AIModelVersion.model_id.in_(model_ids))
    config_ids = select(MonitoringConfig.id).where(
        MonitoringConfig.model_version_id.in_(version_ids)
    )

    counts: dict[str, int] = {}

    async def _run(stmt) -> int:
        res = await db.execute(stmt)
        return res.rowcount or 0

    # 1. Drift alerts (no cascade) tied to this source's model versions/configs —
    #    must go before the models, whose version/config cascade would hit them.
    counts["drift_alerts"] = await _run(
        delete(DriftAlert).where(
            or_(
                DriftAlert.model_version_id.in_(version_ids),
                DriftAlert.monitoring_config_id.in_(config_ids),
            )
        )
    )

    # 2. Lineage edges referencing this source's assets in ANY role — covers the
    #    non-cascading transformation_asset_id as well as source/target.
    counts["lineage_edges"] = await _run(
        delete(LineageEdge).where(
            or_(
                LineageEdge.source_asset_id.in_(asset_ids),
                LineageEdge.target_asset_id.in_(asset_ids),
                LineageEdge.transformation_asset_id.in_(asset_ids),
            )
        )
    )

    # 3. Bias runs that used one of these assets as the test dataset (no cascade).
    counts["bias_test_runs"] = await _run(
        delete(BiasTestRun).where(BiasTestRun.test_dataset_id.in_(asset_ids))
    )

    # 4. Compliance mappings pinned to these assets (no cascade).
    counts["compliance_mappings"] = await _run(
        delete(ComplianceMapping).where(ComplianceMapping.asset_id.in_(asset_ids))
    )

    # 5. Classification results for these assets (cascade-safe, deleted explicitly
    #    so the count is reported and ordering is unambiguous).
    counts["classification_results"] = await _run(
        delete(ClassificationResult).where(ClassificationResult.asset_id.in_(asset_ids))
    )

    # 6. AI models registered against this source — cascades to model versions,
    #    risk assessments, monitoring configs and version-scoped bias runs.
    counts["ai_models"] = await _run(delete(AIModel).where(AIModel.source_id == sid))

    # 7. Classification runs scoped to this source (no cascade on source_id).
    counts["classification_runs"] = await _run(
        delete(ClassificationRun).where(ClassificationRun.source_id == sid)
    )

    # 8. The assets themselves — cascades quality rules/runs/results and any
    #    remaining classification results. parent_id self-references resolve
    #    because all of a source's assets are removed in one statement.
    counts["assets"] = await _run(delete(Asset).where(Asset.source_id == sid))

    # 9. Finally the source row.
    await db.execute(delete(DataSource).where(DataSource.id == sid))
    counts["data_sources"] = 1

    return counts
