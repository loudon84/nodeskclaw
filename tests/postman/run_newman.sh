#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTION="${SCRIPT_DIR}/nodeskclaw_agent_acceptance.postman_collection.json"
ENVIRONMENT="${SCRIPT_DIR}/nodeskclaw_agent_acceptance.postman_environment.json"
REPORTS_DIR="${SCRIPT_DIR}/../../reports"

mkdir -p "${REPORTS_DIR}"

echo "Running NoDeskClaw Agent Acceptance Suite with Newman..."
npx newman run "${COLLECTION}" \
  -e "${ENVIRONMENT}" \
  --reporters cli,junit \
  --reporter-junit-export "${REPORTS_DIR}/newman-report.xml" \
  --delay-request 50

echo "Newman acceptance run completed successfully."
