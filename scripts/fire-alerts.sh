#!/usr/bin/env bash
set -euo pipefail

# Fires synthetic alerts against an Alertmanager instance to verify routing.
# Usage:
#   scripts/fire-alerts.sh [--alertmanager-url URL] [--environment ENV] [--dry-run]
# Environment variables:
#   ALERTMANAGER_URL - Overrides the target Alertmanager URL.
#   ALERT_ENVIRONMENT - Overrides the environment label on alerts.
# Requires:
#   curl, jq

ALERTMANAGER_URL=${ALERTMANAGER_URL:-http://localhost:9093}
ALERT_ENVIRONMENT=${ALERT_ENVIRONMENT:-staging}
DRY_RUN=false

usage() {
  cat <<'USAGE'
Usage: fire-alerts.sh [options]

Options:
  --alertmanager-url URL  Target Alertmanager base URL (default: http://localhost:9093)
  --environment ENV       Value for the environment label (default: staging)
  --dry-run               Print the payload instead of sending it
  -h, --help              Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alertmanager-url)
      [[ $# -lt 2 ]] && { echo "--alertmanager-url requires an argument" >&2; exit 1; }
      ALERTMANAGER_URL="$2"
      shift 2
      ;;
    --environment)
      [[ $# -lt 2 ]] && { echo "--environment requires an argument" >&2; exit 1; }
      ALERT_ENVIRONMENT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to run this script" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to run this script" >&2
  exit 1
fi

now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
if ends_at=$(date -u -v+5M +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null); then
  :
else
  ends_at=$(date -u -d "+5 minutes" +"%Y-%m-%dT%H:%M:%SZ")
fi

payload=$(jq -n \
  --arg env "$ALERT_ENVIRONMENT" \
  --arg starts "$now" \
  --arg ends "$ends_at" \
  '[
    {
      "labels": {
        "alertname": "ClusterJobFailuresHigh",
        "service": "sploot-cluster",
        "severity": "critical",
        "environment": $env
      },
      "annotations": {
        "summary": "Clustering failures exceeded threshold",
        "description": "cluster_jobs_total{outcome!=\"success\"} rate > 1/min for 5 minutes"
      },
      "startsAt": $starts,
      "endsAt": $ends
    },
    {
      "labels": {
        "alertname": "ClusterLatencyP95High",
        "service": "sploot-cluster",
        "severity": "warning",
        "environment": $env
      },
      "annotations": {
        "summary": "Clustering latency p95 above target",
        "description": "cluster_job_duration_seconds p95 > 5s for 10 minutes"
      },
      "startsAt": $starts,
      "endsAt": $ends
    },
    {
      "labels": {
        "alertname": "ClusterFeedbackFailures",
        "service": "sploot-cluster",
        "severity": "critical",
        "environment": $env
      },
      "annotations": {
        "summary": "Merge/Split feedback is failing",
        "description": "cluster_feedback_operations_total{outcome!=\"success\"} increased"
      },
      "startsAt": $starts,
      "endsAt": $ends
    },
    {
      "labels": {
        "alertname": "MediaClusterStreamLagHigh",
        "service": "media-clustering-legacy",
        "severity": "info",
        "environment": $env
      },
      "annotations": {
        "summary": "Legacy worker stream lag check (optional)",
        "description": "media_cluster_stream_lag_seconds > 30s"
      },
      "startsAt": $starts,
      "endsAt": $ends
    }
  ]')

if [[ "$DRY_RUN" == true ]]; then
  echo "=== Alertmanager URL ==="
  echo "$ALERTMANAGER_URL/api/v2/alerts"
  echo "=== Payload ==="
  echo "$payload" | jq '.'
  exit 0
fi

response=$(curl -sS -w '\n%{http_code}' -X POST \
  "$ALERTMANAGER_URL/api/v2/alerts" \
  -H "Content-Type: application/json" \
  -d "$payload")

body=$(echo "$response" | sed '$d')
status=$(echo "$response" | tail -n1)

if [[ "$status" != "200" && "$status" != "202" ]]; then
  echo "Request failed with status $status" >&2
  [[ -n "$body" ]] && echo "$body" >&2
  exit 1
fi

echo "Alerts fired successfully (status $status)"
[[ -n "$body" ]] && echo "$body" | jq '.'
