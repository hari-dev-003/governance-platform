"""FastAPI application entrypoint for the Data + AI Governance Platform."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
import app.models  # noqa: F401  (register all tables)
from app.services.bootstrap import run_bootstrap

logger = logging.getLogger("governance")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure schema exists (idempotent) and seed first-run defaults.
    # For production, prefer `alembic upgrade head`; create_all is a dev convenience.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSessionLocal() as db:
            await run_bootstrap(db)
        logger.info("Startup: schema ready and defaults seeded.")
    except Exception as e:  # noqa: BLE001
        logger.error("Startup bootstrap failed (is Postgres reachable?): %s", e)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="End-to-end Data + AI Governance: catalog, lineage, quality, "
                "classification, AI model registry, risk, bias, drift, compliance, audit.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["meta"])
async def root():
    return {"name": settings.APP_NAME, "version": "1.0.0",
            "docs": "/docs", "api": settings.API_V1_PREFIX}


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
