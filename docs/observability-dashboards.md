# Observability Dashboards & Alerts

## Objective
Deliver end-to-end visibility for the Redis Streams ingestion pipeline before the production feature flag rollout. Dashboards must highlight lag, retries, throughput, and service health with actionable alerting thresholds.

## Metrics Inventory
| Metric | Source | Description | Target | Alert Threshold |
|--------|--------|-------------|--------|-----------------|
| `cluster_jobs_total{outcome="success"}` | `sploot-cluster` Prometheus | Successful clustering jobs per service instance | Monotonic increase | Alert if growth stops for 10 min during active uploads |
| `cluster_jobs_total{outcome!="success"}` | `sploot-cluster` Prometheus | Failed clustering jobs (includes exceptions) | 0 steady-state | Warn if rate > 1/min (5m), critical if > 3/min (5m) |
| `cluster_job_duration_seconds` | `sploot-cluster` histogram | Processing latency by backend (`faiss`, `hdbscan_cpu`, etc.) | p95 < 3s | Warn at p95 > 5s (5m), critical at p95 > 8s (5m) |
| `cluster_feedback_operations_total{outcome!="success"}` | `sploot-cluster` Prometheus | Failed merge/split feedback operations | 0 steady-state | Critical on any increase; auto-page if 2 failures within 10m |
| `cluster_last_noise_count` | `sploot-cluster` gauge | Noise points retained after most recent clustering run | < 15 typical | Warn at > 30 for 3 consecutive runs |
| `media_cluster_pending_jobs` | Legacy worker exporter | Redis pending entries in consumer group (still available in staging) | < 50 | Warn at 100, critical at 250 |
| `media_cluster_stream_lag_seconds` | Legacy worker exporter | Idle time of oldest pending job | < 5s | Warn at 10s, critical at 30s |

## Dashboard Layout (Grafana)
Dashboard JSON: `dashboards/media-clustering-redis-streams.json` (title **“Media Clustering – Pipeline Health”**).

1. **Outcomes Overview**
   - Stat tiles for successful vs. failed jobs.
   - Noise count gauge to spot spikes in low-quality embeddings.
2. **Throughput & Latency**
   - Time series for job throughput (`success/min`, `failures/min`).
   - Histogram quantiles (p50 / p95) for `cluster_job_duration_seconds`.
3. **Feedback Activity**
   - Time series grouped by `operation`/`outcome` showing merge and split volume.
   - Stat tiles summarising cumulative merge/split successes.
4. **Backlog (optional)**
   - If the legacy worker exporter is running, pin the `media_cluster_pending_jobs` and `media_cluster_stream_lag_seconds` charts in an auxiliary row. Otherwise monitor via Redis CLI (`XINFO` / `XPENDING`).

## Alert Routing
- **Primary**: `#sploot-media-alerts` Slack channel
- **PagerDuty**: Media Clustering rotation (critical alerts only)
- Alert policies:
   - `cluster_jobs_total{outcome!="success"}` rate > 1/min for 5 min → PagerDuty (auto-page).
   - `cluster_job_duration_seconds` p95 > 5s for 10 min → Slack warning (tag @oncall); escalate to PagerDuty if > 8s for 10 min.
   - Any increase in `cluster_feedback_operations_total{outcome!="success"}` → PagerDuty (treat as data integrity event).
   - Optional: `media_cluster_stream_lag_seconds` > 30s for 5 min (legacy worker environments) → Slack warning.

## Implementation Tasks
- [x] Export Prometheus metrics from workers (structured logging and metrics milestone)
- [x] Author Grafana dashboard JSON (`dashboards/media-clustering-redis-streams.json`)
- [ ] Deploy Grafana dashboard via `scripts/deploy-dashboards.sh`
- [x] Configure Alertmanager routes (`config/alertmanager.yaml`)
- [ ] Validate alerts fire using `scripts/fire-alerts.sh --dry-run` in staging
- [x] Document dashboard URLs and escalation steps in the runbook

## Runbook & Escalation
### Quick Links
- Grafana dashboard: `https://grafana.staging.sploot.internal/d/media-cluster-observability/media-clustering-%E2%80%93-pipeline-health`
- Prometheus console (staging): `https://prometheus.staging.sploot.internal/graph`
- Loki log search: `https://loki.staging.sploot.internal/explore?orgId=1&left=%5B%22now-1h%22,%22now%22,%22Loki%22,%7B%22expr%22:%22{service=\"sploot-cluster\"}%22%7D%5D`

### Incident Playbooks
1. **Clustering failures spike**
   1. Confirm alert fired from `cluster_jobs_total{outcome!="success"}` panel.
   2. Drill into Grafana panel → view logs (`Explore`) filtered by `logger="sploot-cluster.queue"` and impacted `pet_id`.
   3. Check Redis stream backlog:
      ```bash
      redis-cli -u "$REDIS_URL" XPENDING streams:embedding.ingested cluster-workers
      ```
   4. If particular message is poisoned, acknowledge and requeue manually:
      ```bash
      redis-cli -u "$REDIS_URL" XCLAIM streams:embedding.ingested cluster-workers rescue-consumer 0 <message-id>
      redis-cli -u "$REDIS_URL" XACK streams:embedding.ingested cluster-workers <message-id>
      ```
   5. Escalate to ML on-call if the failure originates from model output (embedding dimensions mismatch, etc.).

2. **Latency regression** (`cluster_job_duration_seconds` p95 alert)
   1. Compare p50 vs p95 to identify tail-only impact.
   2. Check backend label in Grafana (hover tooltip shows `backend_used`). If CPU fallback is active unexpectedly, verify GPU nodes.
   3. Inspect `sploot-cluster` pod resources (Kubernetes):
      ```bash
      kubectl top pod -l app=sploot-cluster -n media
      kubectl describe pod <pod> -n media
      ```
   4. If Redis lag is also rising, coordinate with Platform to scale worker replicas or bump Redis plan.

3. **Noise count surge** (`cluster_last_noise_count`)
   1. Identify affected pet via logs (panel links include `pet_id`).
   2. Trigger manual recluster via auth internal endpoint:
      ```bash
      http --verify false POST "$AUTH_URL/api/v1/internal/clusters/recluster" pet_id:=<id>
      ```
   3. If surge persists, notify data labeling to review embeddings; capture example payload from Redis for offline analysis.

### Redis Backlog Drill
- Inspect consumer group status:
  ```bash
  redis-cli -u "$REDIS_URL" XINFO CONSUMERS streams:embedding.ingested cluster-workers
  ```
- Recover a stuck consumer by recreating it:
  ```bash
  redis-cli -u "$REDIS_URL" XGROUP DELCONSUMER streams:embedding.ingested cluster-workers <consumer-name>
  ```
- Use `scripts/replay_staging_traffic.py` to backfill jobs once backlog clears.

### Post-Incident Checklist
- Annotate Grafana panel with incident summary and timestamp.
- File a follow-up ticket if thresholds need tuning or instrumentation gaps were discovered.
- Update this runbook if new mitigation steps emerge.

## Metrics Endpoint
- Local worker metrics are available at `http://localhost:9105/metrics` when running `docker compose -f docker-compose.local.yml up`.
- Override the bind host/port using `WORKER_METRICS_HOST` and `WORKER_METRICS_PORT` environment variables.

## Deployment Helpers
- Use `scripts/deploy-dashboards.sh` to publish the dashboard once Grafana credentials are available. The script expects `curl` and `jq` to be installed.
- Alert routing configuration lives in `config/alertmanager.yaml`. Populate `SLACK_WEBHOOK_URL` and `PAGERDUTY_ROUTING_KEY` secrets in the deployment environment.

### Example Dashboard Deployment Command
```bash
export GRAFANA_URL="https://grafana.staging.sploot.internal"
export GRAFANA_API_TOKEN="<token with dashboard write scope>"
scripts/deploy-dashboards.sh
```

### Alert Routing Smoke Test
Use `scripts/fire-alerts.sh` to verify Alertmanager routes without waiting for real incidents.

```bash
# Preview the payload without sending requests
scripts/fire-alerts.sh --dry-run

# Send test alerts to a specific Alertmanager instance
ALERTMANAGER_URL="https://alertmanager.prod.sploot.internal" \
   scripts/fire-alerts.sh --environment production
```

## Deliverables
- Grafana dashboard titled **“Media Clustering – Pipeline Health”** (`dashboards/media-clustering-redis-streams.json`)
- Alertmanager configuration PR approved by SRE
- Runbook updates referencing dashboards and alert policies (this document)

## Links
- Staging Grafana: `https://grafana.staging.sploot.internal`
- Prometheus scrape config repo: `https://github.com/sploot/sre-prometheus-config`
- Alertmanager repo: `https://github.com/sploot/sre-alertmanager`
