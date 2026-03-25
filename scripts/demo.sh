#!/usr/bin/env bash
# Demo: health checks and sample chat requests to the agent.
# Usage: ./scripts/demo.sh
#   APP_URL=http://localhost:8001 AGENT_URL=http://localhost:8002 ./scripts/demo.sh

set -euo pipefail

APP_URL="${APP_URL:-http://localhost:8001}"
LLM_URL="${LLM_URL:-http://localhost:8000}"
AGENT_URL="${AGENT_URL:-http://localhost:8002}"

echo "== Demo: edge-agent-demo =="
echo "App:        $APP_URL"
echo "Local LLM:  $LLM_URL"
echo "Agent:      $AGENT_URL"
echo

echo "== Health checks =="
curl -fsS "$APP_URL/health" | jq . 2>/dev/null || curl -fsS "$APP_URL/health"
curl -fsS "$AGENT_URL/health" | jq . 2>/dev/null || curl -fsS "$AGENT_URL/health"
curl -fsS "$LLM_URL/v1/models" | jq '.data[0].id' 2>/dev/null || echo "(models: curl $LLM_URL/v1/models)"
echo

echo "== App: status =="
curl -fsS "$APP_URL/status" | jq . 2>/dev/null || curl -fsS "$APP_URL/status"
echo

echo "== Agent: simple question (expects tools against the app) =="
curl -fsS "$AGENT_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"How many cases are there and how many are overdue? Use tools if you need data."}' \
  | jq . 2>/dev/null || curl -fsS "$AGENT_URL/chat" -H "Content-Type: application/json" \
  -d '{"message":"How many cases are there and how many are overdue? Use tools if you need data."}'
echo

echo "== Agent: search overdue cases =="
curl -fsS "$AGENT_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"List all customer cases with status overdue."}' \
  | jq . 2>/dev/null || curl -fsS "$AGENT_URL/chat" -H "Content-Type: application/json" \
  -d '{"message":"List all customer cases with status overdue."}'
echo

echo "== Done. Open $AGENT_URL in a browser for the UI. =="
