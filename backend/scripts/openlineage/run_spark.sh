#!/usr/bin/env bash
set -e
source ~/sparkenv/bin/activate 2>/dev/null || true

# Topology: Spark in WSL. Postgres = Docker in WSL (localhost:5432).
# Backend (FastAPI) on WINDOWS:8000 -> from WSL that is the Windows host IP, NOT localhost.
if [ -z "$PLATFORM_API" ]; then
  if grep -qi microsoft /proc/version 2>/dev/null; then
    WINHOST=$(ip route show default | awk '{print $3}')
    export PLATFORM_API="http://$WINHOST:8000/api/v1"
  else
    export PLATFORM_API="http://localhost:8000/api/v1"
  fi
fi
export OL_API_KEY="${OL_API_KEY:-my-secret-key}"
export JDBC_URL="${JDBC_URL:-jdbc:postgresql://localhost:5432/sample_shop}"

BASE="${PLATFORM_API%/api/v1}"
echo ">> backend (lineage):  $PLATFORM_API"
echo ">> postgres (jdbc):    $JDBC_URL"

if curl -fsS "$BASE/health" >/dev/null 2>&1; then
  echo ">> backend reachable OK"
else
  echo "!! Cannot reach backend at $BASE from WSL. Fix:"
  echo "   1) On Windows:  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"
  echo "   2) If refused/timeout, allow it (PowerShell admin):"
  echo "      New-NetFirewallRule -DisplayName 'WSL backend 8000' -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow"
  echo "   3) Or set manually:  export PLATFORM_API=http://<windows-ip>:8000/api/v1"
fi

PGHOST=$(echo "$JDBC_URL" | sed -E 's#.*//([^:/]+).*#\1#')
PGPORT=$(echo "$JDBC_URL" | sed -E 's#.*:([0-9]+)/.*#\1#')
if (exec 3<>"/dev/tcp/$PGHOST/$PGPORT") 2>/dev/null; then echo ">> postgres reachable OK"; exec 3>&- 3<&-;
else echo "!! Postgres not reachable at $PGHOST:$PGPORT (container running with -p 5432:5432?)"; fi

echo ""
python shop_to_analytics_spark.py
