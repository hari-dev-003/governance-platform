from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    connection_config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_crawled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    crawl_schedule: Mapped[str] = mapped_column(String(50), server_default=text("'0 2 * * *'"))
    created_by = fk_uuid("users.id")
    created_at: Mapped[datetime.datetime] = created_ts()
    status: Mapped[str] = mapped_column(String(50), server_default=text("'connected'"))
