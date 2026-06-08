from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class LineageEdge(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        Index("idx_lineage_source", "source_asset_id"),
        Index("idx_lineage_target", "target_asset_id"),
    )

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    source_asset_id = fk_uuid("assets.id", ondelete="CASCADE")
    target_asset_id = fk_uuid("assets.id", ondelete="CASCADE")
    transformation_asset_id = fk_uuid("assets.id")
    lineage_type: Mapped[str] = mapped_column(String(50), server_default=text("'technical'"))
    transformation_logic: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, server_default=text("1.0"))
    edge_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime.datetime] = created_ts()
