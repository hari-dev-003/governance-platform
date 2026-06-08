from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class DataPolicy(Base):
    __tablename__ = "data_policies"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False)  # access|retention|usage_purpose|masking
    scope_asset_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    scope_asset_types: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    scope_sensitivity_levels: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by = fk_uuid("users.id")
    approved_by = fk_uuid("users.id")
    effective_from: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = created_ts()


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id")
    requester_id = fk_uuid("users.id")
    asset_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    access_type: Mapped[str] = mapped_column(String(50), nullable=False)  # read|write|admin
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    requested_duration_days: Mapped[int] = mapped_column(Integer, server_default=text("30"))
    status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    reviewed_by = fk_uuid("users.id")
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime.datetime] = created_ts()
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
