# Staging Validation Runbook

> **Status:** Active. Use this abbreviated staging rehearsal to validate the `image.uploaded` → `embedding.ingested` → clustering pipeline before production rollout. Replaces the previously deferred 24-hour soak.

## Objectives
- Confirm event wiring, embedding ingestion, and clustering updates execute successfully in staging.
- Exercise the Pipeline Health dashboard and alert routes end-to-end.
- Capture metrics and incident-response drill notes for the release log.

## Pre-Requisites
1. Feature flag enabled: `ENABLE_EMBEDDING_EVENT_STREAMS=1` for auth + embedder services.
2. Access to staging Redis, Postgres, Grafana, and Alertmanager.
3. Latest dashboard deployed (`dashboards/media-clustering-redis-streams.json`).
4. Reference checklist: `docs/tests/pipeline-health-validation.md`.

## Execution Outline
1. **Dashboard Deploy (if not already live)**
	- `export GRAFANA_URL=...` (staging)
	- `export GRAFANA_API_TOKEN=...`
	- `scripts/deploy-dashboards.sh`
	- Record resulting dashboard URL.
2. **Alert Dry-Run**
	- `scripts/fire-alerts.sh --dry-run --environment staging`
	- `scripts/fire-alerts.sh --alertmanager-url <staging-url> --environment staging`
	- Verify Slack + PagerDuty notifications; acknowledge immediately.
3. **End-to-End Flow Check**
	- Create pet + upload image via auth API (use synthetic staging asset).
	- Trigger embedder worker (`python -m sploot_embedder.worker --once` if idle).
	- Confirm: `cluster_jobs_total` increments, `cluster_last_noise_count` reasonable (<20), `cluster_job_duration_seconds` p95 < 3s.
	- Inspect `photo_insights` table for new embedding.
4. **Redis Backlog Drill (Optional)**
	- `redis-cli -u "$REDIS_URL" XPENDING streams:embedding.ingested cluster-workers`
	- If backlog non-zero, follow remediation in `docs/observability-dashboards.md`.
5. **Incident Simulation (Optional)**
	- Inject malformed payload to trigger failure alert; exercise runbook recovery steps.

## Data to Capture
- Timestamps and screenshots of dashboard panels before/after run.
- Alert payload IDs and notification screenshots.
- `cluster_jobs_total` deltas and noise count values.
- Any manual interventions taken (Redis commands, worker restarts).

## Post-Run Checklist
- Update this document with summary + date.
- Append results to `docs/tests/pipeline-health-validation.md` (Sign-off section).
- Notify stakeholders in team sync with link to updated runbook + metrics.

## Revision History
- **2025-11-01:** Converted deferred soak plan into active staging validation aligned with Pipeline Health checklist.

## Progress Log
- **2025-11-01:** Executed local `scripts/fire-alerts.sh --dry-run --environment staging` to validate payload prior to hitting staging Alertmanager; stored output in `docs/validation-results/alert-dry-run-2025-11-01.json` for release notes.
- **2025-11-01:** Opened request with SRE for staging Grafana API token and Alertmanager maintenance window to proceed with dashboard deploy + live alert fire.
