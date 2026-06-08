#!/usr/bin/env bash
# Start the FastAPI backend with uv (expects Postgres reachable per backend/.env)
set -e
cd "$(dirname "$0")/backend"
uv sync                                  # creates .venv + installs deps from pyproject/uv.lock
uv run alembic upgrade head              # apply database schema
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
