from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[uuid.UUID] = pk_uuid()
    model_id = fk_uuid("ai_models.id", ondelete="CASCADE")
    assessed_by = fk_uuid("users.id")
    questionnaire_responses: Mapped[dict] = mapped_column(JSONB, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)  # high|limited|minimal
    eu_ai_act_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_factors: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    required_actions: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'draft'"))
    approved_by = fk_uuid("users.id")
    created_at: Mapped[datetime.datetime] = created_ts()
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
