#!/usr/bin/env bash
# Start the FastAPI backend (expects Postgres reachable per backend/.env)
set -e
cd "$(dirname "$0")/backend"
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
