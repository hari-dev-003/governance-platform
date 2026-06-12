"""Application settings, loaded from environment / .env (Pydantic Settings v2)."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # ---- App ----
    APP_NAME: str = "Data + AI Governance Platform"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # ---- Database ----
    DATABASE_URL: Optional[str] = None
    DB_USER: str = "user"
    DB_PASSWORD: str = "admin123"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "datagov"

    # ---- Redis / Celery ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- Security ----
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    CREDENTIAL_ENCRYPTION_KEY: Optional[str] = None

    # ---- Bootstrap admin ----
    ADMIN_EMAIL: str = "admin@local"
    ADMIN_PASSWORD: str = "admin123"
    DEFAULT_ORG_NAME: str = "Default Organization"
    DEFAULT_ORG_SLUG: str = "default"

    # ---- OpenLineage ingestion ----
    OPENLINEAGE_API_KEY: str = ""

    # ---- CORS ----
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ----------------------------------------------------------------
    @property
    def async_database_url(self) -> str:
        """Async SQLAlchemy URL (asyncpg) used by the API."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync SQLAlchemy URL (psycopg2) used by Alembic + Celery workers."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    @property
    def fernet_key(self) -> bytes:
        """Return a valid 32-byte url-safe base64 Fernet key.

        If the operator did not provide one, derive a deterministic key from
        SECRET_KEY so the app still boots in dev (NOT recommended for prod).
        """
        if self.CREDENTIAL_ENCRYPTION_KEY:
            return self.CREDENTIAL_ENCRYPTION_KEY.encode()
        digest = self.SECRET_KEY.encode("utf-8").ljust(32, b"0")[:32]
        return base64.urlsafe_b64encode(digest)

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES", mode="before")
    @classmethod
    def _coerce_int(cls, v):
        return int(v) if v is not None and v != "" else 60 * 24


@lru_cache
def get_settings() -> "Settings":
    return Settings()


settings = get_settings()
