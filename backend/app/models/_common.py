"""Shared column factories so every model declares UUID/timestamp columns the same way."""
from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def pk_uuid() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def fk_uuid(target: str, *, nullable: bool = True, ondelete: str | None = None):
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete) if ondelete else ForeignKey(target),
        nullable=nullable,
    )


def created_ts() -> Mapped[_dt.datetime]:
    return mapped_column(DateTime(timezone=True), server_default=text("now()"))
