# Media Clustering Staging Rollout Plan

> **Status:** Ready to execute once SRE supplies the staging Grafana API token and Alertmanager maintenance window.

## Prerequisites
- SRE provides:
  - `GRAFANA_API_TOKEN` with dashboard write scope for staging.
  - 5 minute Alertmanager maintenance window (suppresses paging during synthetic alerts).
- Local artifacts prepared:
  - Dashboard JSON (`dashboards/media-clustering-redis-streams.json`).
  - Alert payload evidence (`docs/validation-results/alert-dry-run-2025-11-01.json`).
  - Staging validation template (`docs/validation-results/staging-validation-template.md`).
- Feature flag plan:
  - Confirm `ENABLE_EMBEDDING_EVENT_STREAMS=1` for auth + embedder service manifests.
- Base image ready for rollout (`sploot/python-base:3.11-cpu`).

## Execution Steps
1. **Dashboard Deployment**
   ```bash
   export GRAFANA_URL="https://grafana.staging.sploot.internal"
   export GRAFANA_API_TOKEN="<from SRE>"
   scripts/deploy-dashboards.sh
   ```
   - Capture API response (`jq` output) and dashboard URL.
2. **Alert Verification**
   ```bash
   export ALERTMANAGER_URL="https://alertmanager.staging.sploot.internal"
   scripts/fire-alerts.sh --alertmanager-url "$ALERTMANAGER_URL" --environment staging
   ```
   - Confirm Slack + PagerDuty notifications; gather timestamps/screenshots.
   - Note maintenance window start/end in validation template.
3. **End-to-End Flow Validation**
   - Follow `docs/staging-soak-rehearsal.md` Execution Outline.
   - Capture metrics snapshots (before/after) from Grafana.
   - Record Redis backlog/cluster metrics in template.
4. **Service Redeploy (Staging)**
   - Update manifests or Helm values with feature flag and new base image (auth, embedder, cluster).
   - Trigger deployment workflow (Argo CD sync or `kubectl rollout restart`).
   - Verify pods healthy (`kubectl get pods -n media`).
5. **Post-Validation Tasks**
   - Complete `docs/validation-results/staging-validation-template.md`.
   - Update `docs/staging-soak-rehearsal.md` progress log with results and metrics.
   - Notify frontend + product that staging is ready for UI tests.

## Evidence Capture Checklist
- Grafana dashboard deployment response (JSON snippet).
- Alertmanager POST response + notification screenshots.
- Metrics screenshots (Pipeline Health dashboard).
- Redis backlog command output.
- Feature flag confirmation (config diff or screenshot).

## Frontend Handoff
- Provide:
  - Dashboard URL.
  - Example pet IDs with fresh clustering results.
  - Summary of validation findings.
- Coordinate time for UI test pass within 24h of redeploy to catch regressions early.

## Production Considerations (when re-enabling observability)
- Provision Prometheus scraping of the clustering worker/API `/metrics` endpoints and reapply the Grafana dashboard (`dashboards/media-clustering-redis-streams.json`) for long-term monitoring.
- Maintain Alertmanager routes for failure/latency alerts; dry-run against the staging environment before promoting changes to production.
- Store `GRAFANA_API_TOKEN`, `ALERTMANAGER_URL`, and feature-flag secrets in the appropriate secret manager (Vault/Kubernetes Secrets) instead of environment variables.
- Enable container image scanning (Trivy) for the shared base image and service images (`sploot/python-base`, `sploot/auth-service`, `sploot/embedder`, `sploot/media-clustering`) as part of CI/CD before production rollout.

## Rollback Plan
- Revert feature flag to `0` and redeploy services if clustering metrics degrade.
- Restore previous dashboard version via Grafana history if needed.
- Disable synthetic alerts by removing maintenance window and running `scripts/fire-alerts.sh --alertmanager-url ... --environment staging --dry-run` to confirm quiet state.
