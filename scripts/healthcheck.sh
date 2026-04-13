#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# healthcheck.sh – ping every service /health endpoint and report status
# Usage:
#   chmod +x scripts/healthcheck.sh
#   ./scripts/healthcheck.sh [--base-url http://localhost]
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

BASE="${1:-http://localhost}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

declare -A SERVICES=(
  ["api-gateway"]="8000"
  ["ingestion-service"]="8001"
  ["rag-service"]="8002"
  ["analytics-service"]="8003"
  ["knowledge-service"]="8004"
  ["agent-orchestrator"]="8005"
  ["llm-service"]="8006"
  ["session-service"]="8007"
)

declare -A INFRA=(
  ["qdrant-ui"]="6333"
  ["prometheus"]="9090"
  ["grafana"]="3001"
  ["jaeger-ui"]="16686"
  ["frontend"]="3000"
)

PASS=0
FAIL=0
WARN=0

check() {
  local name="$1"
  local url="$2"
  local timeout="${3:-5}"

  local start
  start=$(date +%s%N)

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time "$timeout" "$url" 2>/dev/null || echo "000")

  local end
  end=$(date +%s%N)
  local ms=$(( (end - start) / 1000000 ))

  if [[ "$http_code" == "200" ]]; then
    printf "  ${GREEN}✓${RESET}  %-30s ${GREEN}%-4s${RESET}  %dms\n" "$name" "OK" "$ms"
    (( PASS++ ))
  elif [[ "$http_code" == "000" ]]; then
    printf "  ${RED}✗${RESET}  %-30s ${RED}%-4s${RESET}  timeout/refused\n" "$name" "DOWN"
    (( FAIL++ ))
  else
    printf "  ${YELLOW}~${RESET}  %-30s ${YELLOW}%-4s${RESET}  HTTP $http_code  %dms\n" "$name" "WARN" "$ms"
    (( WARN++ ))
  fi
}

echo ""
echo -e "${CYAN}══════════════════════════════════════════════${RESET}"
echo -e "${CYAN}   HealthAI Platform – Service Health Check   ${RESET}"
echo -e "${CYAN}══════════════════════════════════════════════${RESET}"
echo -e "   Base URL: ${BASE}"
echo -e "   Time:     $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""

echo -e "${CYAN}── Microservices ────────────────────────────${RESET}"
for name in "${!SERVICES[@]}"; do
  port="${SERVICES[$name]}"
  check "$name" "${BASE}:${port}/health"
done

echo ""
echo -e "${CYAN}── Infrastructure & UI ──────────────────────${RESET}"
for name in "${!INFRA[@]}"; do
  port="${INFRA[$name]}"
  check "$name" "${BASE}:${port}" 3
done

echo ""
echo -e "${CYAN}── Summary ──────────────────────────────────${RESET}"
echo -e "   ${GREEN}Healthy:  $PASS${RESET}"
[[ $WARN -gt 0 ]] && echo -e "   ${YELLOW}Warning:  $WARN${RESET}"
[[ $FAIL -gt 0 ]] && echo -e "   ${RED}Down:     $FAIL${RESET}"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo -e "  ${RED}⚠  Some services are down. Check: docker compose ps${RESET}"
  echo ""
  exit 1
elif [[ $WARN -gt 0 ]]; then
  echo -e "  ${YELLOW}⚠  Some services returned non-200. Check logs.${RESET}"
  echo ""
  exit 0
else
  echo -e "  ${GREEN}All services healthy ✓${RESET}"
  echo ""
  exit 0
fi
