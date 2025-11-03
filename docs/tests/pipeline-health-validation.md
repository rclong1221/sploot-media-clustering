# Pipeline Health Validation Checklist

Use this checklist after deploying the **Media Clustering – Pipeline Health** dashboard and alert policies.

## 1. Grafana Dashboard Deployment
- [ ] Set `GRAFANA_URL` and `GRAFANA_API_TOKEN` (staging) and run `scripts/deploy-dashboards.sh`.
- [ ] Repeat for production once staging validation passes.
- [ ] Capture dashboard URLs for release notes.

## 2. Alert Dry-Run
- [ ] Schedule a maintenance window (5 min) to avoid paging on-call.
- [x] Run `scripts/fire-alerts.sh --dry-run --environment staging` and confirm payload. _(2025-11-01: verified locally, captured payload for release notes; staging Alertmanager send still pending.)_
- [ ] Run `scripts/fire-alerts.sh --alertmanager-url <staging-url> --environment staging`.
- [ ] Verify Slack notification landed in `#sploot-media-alerts` with correct severity.
- [ ] Confirm PagerDuty (critical alerts) triggered once (ack immediately).
- [ ] Document timestamps and screenshots in release notes.
	> Fill out `docs/validation-results/staging-validation-template.md` when capturing evidence.

## 3. Staging Flow Validation
- [ ] Enable feature flag: `ENABLE_EMBEDDING_EVENT_STREAMS=1` in staging.
- [ ] Upload test pet + image via auth API.
- [ ] Tail auth logs for `Embedding ingestion succeeded` and check `photo_insights` record.
- [ ] Trigger embedder worker manually if needed (`python -m sploot_embedder.worker --once`).
- [ ] Confirm `cluster_jobs_total{outcome="success"}` increments and noise count reasonable (<20).
- [ ] Ensure `cluster_job_duration_seconds` p95 stays < 3s during run.

## 4. Incident Drill (Optional)
- [ ] Simulate failure by injecting malformed Redis payload and ensure alert fires.
- [ ] Use runbook steps to recover (requeue, ack, etc.).

## 5. Sign-off
- [ ] Write summary in `docs/staging-soak-rehearsal.md` with metrics snapshots.
- [ ] Communicate completion in team sync with runbook link.

## Progress Notes
- 2025-11-01: Dry-run payload validated locally; payload archived at `docs/validation-results/alert-dry-run-2025-11-01.json`. Requested staging Grafana API token and Alertmanager maintenance window; staging alert send and on-call verification remain. Prepared `docs/validation-results/staging-validation-template.md` for the final report.
