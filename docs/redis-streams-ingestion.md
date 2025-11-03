# Redis Streams Ingestion Plan

## Goals
- Adopt Redis Streams as the production message backbone between upstream media ingestion and the clustering worker fleet.
- Provide reliable, observable delivery semantics (at-least-once) without introducing BullMQ or sidecar brokers.
- Support both the existing local Docker Compose environment and the future production deployment.

## Status (Oct 30, 2025)
- [x] Local Redis Streams pipeline wired end-to-end (auth producer → worker consumer).
- [x] Docker Compose updated for Redis AOF persistence and new stream env vars.
- [x] Feature flag + HTTP fallback implemented in auth-service.
- [x] Worker retry/dead-letter handling exercised locally.
- [x] Integration/CI tests with `fakeredis`.
- [ ] Production infra/Terraform definitions.
- [ ] Runbook + observability dashboards.

## Non-Goals
- Replacing Redis with another broker technology.
- Implementing persistence of clustering results (covered by a later milestone).
- Redesigning upstream auth-service payload schemas.

## Current State
- Auth service enqueues HTTP callbacks to the media clustering API.
- The clustering worker reads from an in-memory stub; jobs are not persisted and retry semantics are absent.
- Deployment uses a single worker process and does not expose health or metrics endpoints.

## Proposed Design
1. **Stream Definition**
   - Stream key: `streams:media.cluster`
   - Consumer group: `media-clustering-workers`
   - Consumer name: `media-clustering-worker-${HOSTNAME}`
2. **Message Schema**
   ```json
   {
     "job_id": "ulid",
     "pet_id": "uuid",
     "image_ids": ["uuid"],
     "reason": "string",
     "force": false,
     "quality_score": 0.95,
     "metadata": {
       "emitted_at": "iso-8601",
       "source": "auth-service"
     }
   }
   ```
3. **Producer (auth-service)**
   - On image ingest, publish to the stream using `XADD stream * field value` with a maxlen policy configured via Redis config (`XADD ... MAXLEN ~ 1000000`).
   - Include `trace_id` in metadata for cross-service correlation.
4. **Consumer (media-clustering worker)**
   - Use blocking `XREADGROUP GROUP media-clustering-workers ${consumer} BLOCK 5000 COUNT 16 STREAMS streams:media.cluster >`.
   - Acknowledge processed messages via `XACK` only after downstream tasks succeed.
   - Track in-flight workload in memory to avoid duplicate processing inside a single worker.
5. **Retry & Dead-Letter Handling**
   - Use `XPENDING` to detect idle messages older than `retry_idle_ms` (default 60000 ms).
   - Reclaim stalled jobs with `XCLAIM` and increment an attempt counter stored in message metadata.
   - When `attempts >= 5`, move the message to `streams:media.cluster.deadletter` and raise an alert.
6. **Backpressure**
   - If worker backlog exceeds `max_pending_per_worker` (configurable, default 256), stop claiming new messages and emit Prometheus alerts.

## Configuration Matrix

| Setting | Dev Default | Production Default |
| --- | --- | --- |
| `REDIS_URL` | `redis://media-redis:6379/0` | TLS-enabled Redis endpoint (AWS Elasticache or Azure Cache) |
| `CLUSTER_STREAM_KEY` | `streams:media.cluster` | Same; override via env if namespace differs |
| `CLUSTER_CONSUMER_GROUP` | `media-clustering-workers` | Team-specific group name |
| `CLUSTER_WORKER_CONSUMER_NAME` | `dev-worker` | Pod hostname or StatefulSet ordinal |
| `STREAM_MAXLEN` | `10000` | `1000000` |
| `RETRY_IDLE_MS` | `60000` | `30000` |
| `MAX_ATTEMPTS` | `5` | `5` |
| `MAX_PENDING_PER_WORKER` | `64` | `256` |

## Observability
- **Metrics**: Expose Prometheus counters/gauges for enqueued jobs, acked jobs, retries, dead-letter count, lag, and processing latency.
- **Logs**: Use structured logging capturing `job_id`, `pet_id`, `attempt`, `trace_id`.
- **Tracing**: Propagate OpenTelemetry context from auth-service (span in HTTP handler) to worker; attach `job_id` as span attribute.
- **Health Checks**: Add `/internal/health/redis` endpoint verifying latency of `PING` and availability of consumer group.
- **Current status**: Worker emits JSON logs with job metadata and exposes Prometheus metrics at `/metrics` (see `observability-dashboards.md`).
- **Alerting**: Alertmanager routing configuration is defined in `config/alertmanager.yaml`; staging environment must provide Slack and PagerDuty credentials prior to the soak.

## Production Canary Rollout Plan
- **Canary enablement**: Use the feature flag `redis_streams_media_cluster_enabled` to roll out to 10% of production tenants while watching stream lag, retry, and fallback metrics for 30 minutes.
- **Ramp strategy**: If canary tenants remain healthy, increase to 50% for an additional 60 minutes; proceed to 100% once alerts stay green. Detailed steps are documented in `production-rollout.md`.
- **Rollback**: Immediately toggle the flag back to 0% if lag, retries, or downstream errors exceed thresholds. Maintain the HTTP enqueue fallback path until post-rollout stability is achieved.
- **Fallback removal**: After 24–48 hours of steady-state success at 100%, remove the HTTP fallback code path in auth-service and clean up the feature flag configuration.
- **Runbook updates**: Align documentation in `observability-dashboards.md` and `production-rollout.md` so on-call engineers have current procedures.

## Deployment Steps
1. Update `sploot-auth-service` to publish to Redis Streams using environment-driven configuration.
2. Add Redis client pool to the clustering service (`redis.asyncio` preferred for async workers).
3. Implement consumer loop with cooperative cancellation and graceful shutdown (`SIGTERM` handling).
4. Write acceptance tests using `fakeredis` to validate stream semantics and retry logic.
5. Update Docker Compose to run Redis with persistence (Append Only File) in dev.
6. Define production Terraform/Helm values (Redis endpoints, secrets, autoscaling target CPU/memory for workers).

## Risk Mitigation
- Circuit breaker on Redis connectivity to avoid cascading failures.
- Feature flag to toggle between HTTP enqueue fallback and Redis Streams while rolling out.
- Load test with synthetic traffic to confirm throughput and latency budgets.

## Validation Plan
- Unit tests covering producer and consumer helpers.
- Integration tests spinning up Redis in CI.
- Runbook with `XINFO GROUPS` and `XPENDING` diagnostics.
- Chaos test by killing worker pods to ensure `XCLAIM` recovers stuck jobs.
