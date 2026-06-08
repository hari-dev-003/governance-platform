from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, Float, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class BiasTestRun(Base):
    __tablename__ = "bias_test_runs"

    id: Mapped[uuid.UUID] = pk_uuid()
    model_version_id = fk_uuid("ai_model_versions.id", ondelete="CASCADE")
    test_dataset_id = fk_uuid("assets.id")
    triggered_by = fk_uuid("users.id")

    protected_attributes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    label_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prediction_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    positive_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(50), server_default=text("'running'"))
    overall_bias_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)

    demographic_parity: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    equal_opportunity: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    predictive_parity: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    individual_fairness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime.datetime] = created_ts()
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
