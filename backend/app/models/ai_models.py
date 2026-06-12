from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._common import created_ts, fk_uuid, pk_uuid


class AIModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = pk_uuid()
    org_id = fk_uuid("organizations.id", ondelete="CASCADE")
    source_id = fk_uuid("data_sources.id")
    external_id: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_id = fk_uuid("users.id")
    team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    use_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # unacceptable | high | limited | minimal | unclassified
    risk_tier: Mapped[str] = mapped_column(String(20), server_default=text("'unclassified'"))
    risk_assessment_status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    deployment_status: Mapped[str] = mapped_column(String(50), server_default=text("'development'"))

    framework: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    technical_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    created_at: Mapped[datetime.datetime] = created_ts()
    updated_at: Mapped[datetime.datetime] = created_ts()


class AIModelVersion(Base):
    __tablename__ = "ai_model_versions"

    id: Mapped[uuid.UUID] = pk_uuid()
    model_id = fk_uuid("ai_models.id", ondelete="CASCADE")
    version_number: Mapped[str] = mapped_column(String(50), nullable=False)
    external_version_id: Mapped[str | None] = mapped_column(String(500), nullable=True)

    trained_by = fk_uuid("users.id")
    training_dataset_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    training_started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    training_completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    metrics: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    hyperparameters: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    input_schema: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    output_schema: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    stage: Mapped[str] = mapped_column(String(50), server_default=text("'development'"))
    validation_status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    validated_by = fk_uuid("users.id")
    validated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Persisted SHAP global feature importance from the last explainability run.
    feature_importance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = created_ts()
