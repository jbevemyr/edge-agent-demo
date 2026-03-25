#!/usr/bin/env bash
# Demo: health checks, warehouse API summary, sample chat to the edge agent.
# Usage: ./scripts/demo.sh
#   APP_URL=http://localhost:8001 AGENT_URL=http://localhost:8002 ./scripts/demo.sh

set -euo pipefail

APP_URL="${APP_URL:-http://localhost:8001}"
LLM_URL="${LLM_URL:-http://localhost:8000}"
AGENT_URL="${AGENT_URL:-http://localhost:8002}"

echo "== Demo: warehouse edge agent =="
echo "App:        $APP_URL"
echo "Local LLM:  $LLM_URL"
echo "Agent:      $AGENT_URL"
echo

echo "== Health checks =="
curl -fsS "$APP_URL/health" | jq . 2>/dev/null || curl -fsS "$APP_URL/health"
curl -fsS "$AGENT_URL/health" | jq . 2>/dev/null || curl -fsS "$AGENT_URL/health"
curl -fsS "$LLM_URL/v1/models" | jq '.data[0].id' 2>/dev/null || echo "(models: curl $LLM_URL/v1/models)"
echo

echo "== App: operations summary =="
curl -fsS "$APP_URL/v1/operations/summary" | jq . 2>/dev/null || curl -fsS "$APP_URL/v1/operations/summary"
echo

echo "== Agent: warehouse snapshot (expects tools) =="
curl -fsS "$AGENT_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"Give a short operations snapshot: how many open events by severity, how many SKUs below reorder, and next shipment cutoffs. Use tools."}' \
  | jq . 2>/dev/null || curl -fsS "$AGENT_URL/chat" -H "Content-Type: application/json" \
  -d '{"message":"Give a short operations snapshot: how many open events by severity, how many SKUs below reorder, and next shipment cutoffs. Use tools."}'
echo

echo "== Agent: critical events at WH-EU-01 =="
curl -fsS "$AGENT_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"List open critical or warning events for warehouse WH-EU-01."}' \
  | jq . 2>/dev/null || curl -fsS "$AGENT_URL/chat" -H "Content-Type: application/json" \
  -d '{"message":"List open critical or warning events for warehouse WH-EU-01."}'
echo

echo "== Done. Open $AGENT_URL in a browser for the UI. =="
