from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class MonitoringConfig(Base):
    __tablename__ = "monitoring_configs"

    id: Mapped[uuid.UUID] = pk_uuid()
    model_version_id = fk_uuid("ai_model_versions.id", ondelete="CASCADE")
    endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, server_default=text("60"))
    psi_threshold: Mapped[float] = mapped_column(Float, server_default=text("0.2"))
    accuracy_degradation_threshold: Mapped[float] = mapped_column(Float, server_default=text("0.05"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = created_ts()


class DriftAlert(Base):
    __tablename__ = "drift_alerts"

    id: Mapped[uuid.UUID] = pk_uuid()
    model_version_id = fk_uuid("ai_model_versions.id")
    monitoring_config_id = fk_uuid("monitoring_configs.id")
    drift_type: Mapped[str] = mapped_column(String(50), nullable=False)  # data|concept|label
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # warning|critical
    affected_features: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    detection_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'open'"))
    acknowledged_by = fk_uuid("users.id")
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime.datetime] = created_ts()
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
