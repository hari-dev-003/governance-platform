from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class ClassificationRule(Base):
    __tablename__ = "classification_rules"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # PII, PHI, PCI, IP, Financial
    sensitivity_level: Mapped[str] = mapped_column(String(50), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(50), nullable=False)  # regex|ml_model|keyword
    pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    is_system_rule: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = created_ts()


class ClassificationResult(Base):
    __tablename__ = "classification_results"

    id: Mapped[uuid.UUID] = pk_uuid()
    asset_id = fk_uuid("assets.id", ondelete="CASCADE")
    rule_id = fk_uuid("classification_rules.id")
    run_id = fk_uuid("classification_runs.id", ondelete="CASCADE")
    detected_category: Mapped[str] = mapped_column(String(100), nullable=False)
    sensitivity_level: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime.datetime] = created_ts()
    reviewed_by = fk_uuid("users.id")
    review_status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ClassificationRun(Base):
    __tablename__ = "classification_runs"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    source_id = fk_uuid("data_sources.id")
    scan_type: Mapped[str] = mapped_column(String(30), nullable=False)   # classification | privacy
    engine: Mapped[str] = mapped_column(String(40), nullable=False)      # rules | presidio
    columns_scanned: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    total_findings: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    started_at: Mapped[datetime.datetime] = created_ts()
