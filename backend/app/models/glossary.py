from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_glossary_name"),)

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # draft | pending_approval | approved | deprecated
    status: Mapped[str] = mapped_column(String(50), server_default=text("'draft'"))
    steward_id = fk_uuid("users.id")
    approved_by = fk_uuid("users.id")
    approved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    parent_term_id = fk_uuid("glossary_terms.id")
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by = fk_uuid("users.id")
    created_at: Mapped[datetime.datetime] = created_ts()
    updated_at: Mapped[datetime.datetime] = created_ts()


class TermAssetLink(Base):
    __tablename__ = "term_asset_links"
    __table_args__ = (UniqueConstraint("term_id", "asset_id", name="uq_term_asset"),)

    id: Mapped[uuid.UUID] = pk_uuid()
    term_id = fk_uuid("glossary_terms.id", ondelete="CASCADE")
    asset_id = fk_uuid("assets.id", ondelete="CASCADE")
    linked_by = fk_uuid("users.id")
    linked_at: Mapped[datetime.datetime] = created_ts()
