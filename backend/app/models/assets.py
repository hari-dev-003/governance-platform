from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean, DateTime, Float, Index, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("org_id", "source_id", "external_id", name="uq_asset_external"),
        Index("idx_assets_org", "org_id"),
        Index("idx_assets_type", "asset_type"),
        Index("idx_assets_source", "source_id"),
        Index("idx_assets_parent", "parent_id"),
        Index("idx_assets_sensitivity", "sensitivity_level"),
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    source_id = fk_uuid("data_sources.id", ondelete="CASCADE")
    external_id: Mapped[str] = mapped_column(String(1000), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id = fk_uuid("assets.id")

    owner_id = fk_uuid("users.id")
    steward_id = fk_uuid("users.id")
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sensitivity_level: Mapped[str] = mapped_column(
        String(50), server_default=text("'unclassified'")
    )

    technical_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))

    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    first_seen_at: Mapped[datetime.datetime] = created_ts()
    last_crawled_at: Mapped[datetime.datetime] = created_ts()
    created_at: Mapped[datetime.datetime] = created_ts()
