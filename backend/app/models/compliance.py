from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class ComplianceFramework(Base):
    __tablename__ = "compliance_frameworks"

    id: Mapped[uuid.UUID] = pk_uuid()
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # GDPR, DPDPA, EU_AI_ACT, PCI_DSS
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system_framework: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = created_ts()


class ComplianceRequirement(Base):
    __tablename__ = "compliance_requirements"

    id: Mapped[uuid.UUID] = pk_uuid()
    framework_id = fk_uuid("compliance_frameworks.id")
    article_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    applies_to_risk_tiers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)


class ComplianceMapping(Base):
    __tablename__ = "compliance_mappings"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id")
    requirement_id = fk_uuid("compliance_requirements.id")
    asset_id = fk_uuid("assets.id")
    status: Mapped[str] = mapped_column(String(50), server_default=text("'not_started'"))
    evidence_links: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to = fk_uuid("users.id")
    due_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = created_ts()
