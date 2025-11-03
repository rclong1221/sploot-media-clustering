# Production Feature Flag Rollout Plan

## Objective
Enable the Redis Streams pipeline in production without a prolonged staging soak by using a tightly monitored canary rollout.

## Prerequisites
- Redis Streams producer already feature-flagged in auth-service (`redis_streams_media_cluster_enabled`).
- Media clustering worker with metrics/logging deployed to production environment.
- Alertmanager routing configured (see `config/alertmanager.yaml`) with production secrets.
- On-call rotation aware of rollout window.

## Rollout Steps
1. **Pre-flight checklist (T-1 day)**
   - Confirm latest images deployed to production.
   - Verify worker metrics reachable via internal Prometheus scrape or `curl` against the metrics endpoint.
   - Ensure PagerDuty/Slack alerts in Alertmanager test successfully (`scripts/fire-alerts.sh --dry-run`).
   - Announce rollout window in `#sploot-media` with escalation chain.

2. **Canary enablement (T0)**
   - Set feature flag to `redis_streams_media_cluster_enabled=0.1` (10% of tenants) using LaunchDarkly/FF service.
   - Monitor metrics for 30 minutes:
     - `media_cluster_jobs_processed_total{result="retry"}` rate < 1/min.
     - `media_cluster_pending_jobs` < 50.
     - `media_cluster_stream_lag_seconds` < 5.
   - Inspect worker JSON logs for errors.

3. **Ramp to 50% (T0 + 30m)**
   - Increase flag to 0.5 if canary healthy.
   - Continue monitoring for 60 minutes; page SRE if alerts trigger.

4. **Full rollout (T0 + 90m)**
   - Increase flag to 1.0.
   - Disable HTTP fallback flag in auth-service when metrics remain green for an additional 24 hours.

5. **Post-rollout**
   - Capture summary in release notes (metrics snapshot, incidents, lessons learned).
   - Remove residual staging soak references from documentation.

## Rollback Plan
- Toggle feature flag back to 0.0 to revert to HTTP fallback immediately.
- If worker issues persist, scale worker deployment to zero and re-enable HTTP-only path in auth-service environment variables.
- Post incident summary in `#sploot-media` if rollback occurs.

## Monitoring Checklist
- `media_cluster_jobs_processed_total` (success vs retry vs dead_letter)
- `media_cluster_job_processing_seconds` histogram (p95 latency)
- `media_cluster_pending_jobs`
- Auth-service HTTP enqueue success metrics for regression comparison.

## Communication
- Primary channel: `#sploot-media`
- Incident paging: Media Clustering PagerDuty service
- Runbook updates: `docs/redis-streams-ingestion.md`
