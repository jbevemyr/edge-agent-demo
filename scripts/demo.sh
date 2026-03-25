#!/usr/bin/env bash
# Demo: kontrollerar tjänster och skickar exempelfrågor till agenten.
# Användning: ./scripts/demo.sh
#   APP_URL=http://localhost:8001 AGENT_URL=http://localhost:8002 ./scripts/demo.sh

set -euo pipefail

APP_URL="${APP_URL:-http://localhost:8001}"
LLM_URL="${LLM_URL:-http://localhost:8000}"
AGENT_URL="${AGENT_URL:-http://localhost:8002}"

echo "== Demo: edge-agent-demo =="
echo "App:       $APP_URL"
echo "Lokal LLM: $LLM_URL"
echo "Agent:     $AGENT_URL"
echo

echo "== Hälsokontroller =="
curl -fsS "$APP_URL/health" | jq . 2>/dev/null || curl -fsS "$APP_URL/health"
curl -fsS "$AGENT_URL/health" | jq . 2>/dev/null || curl -fsS "$AGENT_URL/health"
curl -fsS "$LLM_URL/v1/models" | jq '.data[0].id' 2>/dev/null || echo "(modeller: curl $LLM_URL/v1/models)"
echo

echo "== App: status =="
curl -fsS "$APP_URL/status" | jq . 2>/dev/null || curl -fsS "$APP_URL/status"
echo

echo "== Agent: enkel fråga (förväntat: verktyg mot appen) =="
curl -fsS "$AGENT_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hur många ärenden finns och hur många är försenade? Använd verktyg om du behöver data."}' \
  | jq . 2>/dev/null || curl -fsS "$AGENT_URL/chat" -H "Content-Type: application/json" \
  -d '{"message":"Hur många ärenden finns och hur många är försenade? Använd verktyg om du behöver data."}'
echo

echo "== Agent: sök försenade ärenden =="
curl -fsS "$AGENT_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"Lista alla kundärenden med status overdue."}' \
  | jq . 2>/dev/null || curl -fsS "$AGENT_URL/chat" -H "Content-Type: application/json" \
  -d '{"message":"Lista alla kundärenden med status overdue."}'
echo

echo "== Klart. Öppna gärna $AGENT_URL i webbläsaren för UI. =="
