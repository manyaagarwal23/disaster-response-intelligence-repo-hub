#!/usr/bin/env bash
# One-command-start smoke test.
#
# Brings the whole stack up FROM SCRATCH in an isolated compose project
# (its own fresh volume, port 8001 so a running dev instance on 8000 is
# untouched), waits for the container to fetch Ushahidi and build the
# vector database, asks one real question, and writes the outcome to
# reports/compose-smoke-<date>.log. Cleans up its containers and volume
# at the end.
#
# Usage:  scripts/smoke_test_compose.sh          (takes ~40 min on a 4-CPU VM)
#         SMOKE_BUILD=1 scripts/smoke_test_compose.sh   also rebuild the image
#         (CI already proves the build; a rebuild here needs ~7 GB of disk)
set -uo pipefail

cd "$(dirname "$0")/.."

PROJECT=drihsmoke
export PORT=${SMOKE_PORT:-8001}
REPORT="reports/compose-smoke-$(date +%Y-%m-%d).log"
MAX_WAIT_MIN=${SMOKE_MAX_WAIT_MIN:-90}
BUILD_FLAG=$([ "${SMOKE_BUILD:-0}" = "1" ] && echo "--build" || echo "")

mkdir -p reports
exec > >(tee "$REPORT") 2>&1

compose() { docker compose -p "$PROJECT" "$@"; }

cleanup() {
    echo; echo "== cleanup ($(date +%H:%M:%S))"
    compose down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== compose smoke test started $(date '+%Y-%m-%d %H:%M:%S') on port $PORT"
echo "== commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

compose down -v --remove-orphans >/dev/null 2>&1 || true

echo; echo "== docker compose up $BUILD_FLAG -d"
if ! compose up $BUILD_FLAG -d; then
    echo "RESULT: FAIL (compose up failed)"; exit 1
fi

echo; echo "== waiting for the vector database (first start fetches Ushahidi + builds it)"
start=$(date +%s)
ready=false
while [ $(( ($(date +%s) - start) / 60 )) -lt "$MAX_WAIT_MIN" ]; do
    body=$(curl -s "http://localhost:$PORT/healthz" || true)
    if echo "$body" | grep -q '"database_ready":true'; then ready=true; break; fi
    state=$(docker inspect -f '{{.State.Status}}' "${PROJECT}-rag-1" 2>/dev/null || echo missing)
    if [ "$state" != "running" ]; then
        echo "container state: $state"; compose logs --tail 40; echo "RESULT: FAIL (container stopped)"; exit 1
    fi
    sleep 30
done

elapsed=$(( $(date +%s) - start ))
if [ "$ready" != true ]; then
    compose logs --tail 40; echo "RESULT: FAIL (database not ready after $MAX_WAIT_MIN min)"; exit 1
fi
echo "database ready after $((elapsed / 60)) min $((elapsed % 60)) s"

echo; echo "== container log (ingestion summary)"
compose logs --no-log-prefix 2>&1 | tr '\r' '\n' | grep -E "Fetching|Building|INGESTION|Chunks:|ChromaDB documents|Uvicorn running|Error|Traceback" | head -20

echo; echo "== asking a question"
q='Where is an incoming SMS report parsed?'
t0=$(date +%s.%N)
resp=$(curl -s -X POST "http://localhost:$PORT/api/ask" -H 'Content-Type: application/json' -d "{\"question\":\"$q\"}")
t1=$(date +%s.%N)
echo "question: $q"
echo "answered in $(printf '%.1f' "$(echo "$t1 - $t0" | bc)") s"
echo "$resp" | python3 -c '
import sys, json
r = json.load(sys.stdin)
a = r.get("answer") or {}
print("llm_used:", r.get("llm_used"), "| warning:", r.get("warning"), "| error:", r.get("error"))
print("diagram:", bool(a.get("diagram_code")), "| sources:", [s["file"].rsplit("/", 1)[-1] + ":" + str(s["start_line"]) for s in r.get("sources", [])][:3])
ok = bool(r.get("sources")) and not r.get("error")
print("RESULT:", "PASS" if ok else "FAIL (no sources returned)")
sys.exit(0 if ok else 1)
'
