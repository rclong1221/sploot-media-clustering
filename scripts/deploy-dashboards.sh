#!/usr/bin/env bash
set -euo pipefail

# Deploys Grafana dashboards using the HTTP API.
# Requires the following environment variables:
#   GRAFANA_URL       - Base URL, e.g. https://grafana.staging.sploot.internal
#   GRAFANA_API_TOKEN - API token with dashboard:write permissions
#   DASHBOARD_FILE    - Path to dashboard JSON (defaults to dashboards/media-clustering-redis-streams.json)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DASHBOARD_FILE="${DASHBOARD_FILE:-${ROOT_DIR}/dashboards/media-clustering-redis-streams.json}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to run this script" >&2
  exit 1
fi

if [[ -z "${GRAFANA_URL:-}" ]]; then
  echo "GRAFANA_URL must be set" >&2
  exit 1
fi

if [[ -z "${GRAFANA_API_TOKEN:-}" ]]; then
  echo "GRAFANA_API_TOKEN must be set" >&2
  exit 1
fi

if [[ ! -f "${DASHBOARD_FILE}" ]]; then
  echo "Dashboard file not found: ${DASHBOARD_FILE}" >&2
  exit 1
fi

echo "Deploying ${DASHBOARD_FILE} to ${GRAFANA_URL}" >&2

payload=$(jq -n --argfile dashboard "${DASHBOARD_FILE}" '{dashboard: $dashboard, folderId: 0, overwrite: true}')

curl -sS -X POST "${GRAFANA_URL}/api/dashboards/db" \
  -H "Authorization: Bearer ${GRAFANA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${payload}" |
  jq '.'
