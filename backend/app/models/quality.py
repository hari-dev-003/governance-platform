from __future__ import annotations

import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class QualityRule(Base):
    __tablename__ = "quality_rules"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    asset_id = fk_uuid("assets.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), server_default=text("'warning'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by = fk_uuid("users.id")
    created_at: Mapped[datetime.datetime] = created_ts()


class QualityCheckRun(Base):
    __tablename__ = "quality_check_runs"

    id: Mapped[uuid.UUID] = pk_uuid()
    asset_id = fk_uuid("assets.id", ondelete="CASCADE")
    run_at: Mapped[datetime.datetime] = created_ts()
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_rules: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed_rules: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_rules: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class QualityCheckResult(Base):
    __tablename__ = "quality_check_results"

    id: Mapped[uuid.UUID] = pk_uuid()
    run_id = fk_uuid("quality_check_runs.id", ondelete="CASCADE")
    rule_id = fk_uuid("quality_rules.id", ondelete="CASCADE")
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # passed|failed|error
    records_evaluated: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    records_failed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    failure_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_failures: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    checked_at: Mapped[datetime.datetime] = created_ts()
