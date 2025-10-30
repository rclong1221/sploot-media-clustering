# Tracing & Metrics Integration Plan

## Goals
- Provide end-to-end observability for media clustering jobs across auth-service, Redis Streams, and the clustering worker/API.
- Standardize on the Sploot stack’s telemetry conventions (OpenTelemetry traces, Prometheus metrics, structured logs).
- Support local developers with lightweight exporters and production with managed telemetry backends (e.g., Datadog, New Relic, or OpenTelemetry Collector).

## Non-Goals
- Building a custom monitoring dashboard (we will feed into existing Grafana/New Relic boards).
- Alert policy design (handled by SRE once metrics are emitted).

## Telemetry Components
1. **Tracing**
   - Use OpenTelemetry SDK for Python in both auth-service and media clustering worker/API.
   - Propagate trace context via HTTP headers and Redis message metadata (`traceparent`).
   - Instrument key spans: image upload handler, job enqueue, worker processing stages (embed, cluster, hero selection), Postgres writes.
2. **Metrics**
   - Expose /metrics endpoints using Prometheus client library.
   - Core metrics:
     - Counters: `media_cluster_jobs_total{status}`, `media_cluster_retries_total`, `media_cluster_deadletter_total`.
     - Histograms: `media_cluster_processing_duration_seconds`, `media_cluster_embedding_duration_seconds`, `media_cluster_postgres_write_seconds`.
     - Gauges: `media_cluster_pending_jobs`, `media_cluster_worker_inflight`.
   - Link metrics with labels: `pet_id`, `cluster_version`, `model_version` (avoid high-cardinality by hashing pet_id or using buckets where necessary).
3. **Logging**
   - Structured JSON logs with `trace_id`, `span_id`, `job_id`, `pet_id`, `module`.
   - Integrate with Sploot logging formatter; ensure log level overrides via environment variable.

## Environment Configuration

| Setting | Dev Default | Production Default |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` (docker compose) | Managed collector endpoint |
| `OTEL_SERVICE_NAME` | `sploot-media-clustering` | same |
| `PROMETHEUS_MULTIPROC_DIR` | `/tmp/prometheus` | Directory mounted in Gunicorn/Uvicorn workers |
| `LOG_LEVEL` | `DEBUG` | `INFO` |
| `TRACE_SAMPLE_RATE` | 1.0 (dev) | 0.2 (prod, adjustable) |

## Code Changes
- Initialize OpenTelemetry tracer/provider in app startup; configure resource attributes (env, service version).
- Wrap Redis publisher and consumer with trace instrumentation; attach span attributes for stream name, message ID.
- Use middleware for FastAPI to record request spans; extend worker loop with manual spans for long-running tasks.
- Expose metrics endpoint via FastAPI router (`/internal/metrics`) guarded by internal auth.
- Update Docker Compose to run OpenTelemetry Collector + Prometheus in dev.

## Deployment Considerations
- For production, route telemetry to existing collector agents (DaemonSet or sidecar).
- Ensure environment variables/secrets are set via Terraform/Helm.
- If using gunicorn/uvicorn multi-worker, configure Prometheus multiprocess mode.

## Validation Checklist
- Run `otel-cli status` in dev to confirm traces reach collector.
- Use `prometheus_client` test harness to assert metric names and labels.
- End-to-end test: upload an image → verify trace in backend → confirm metrics increment.
- Load test to ensure telemetry overhead <5% of processing time.

## Rollout Steps
1. Add telemetry dependencies to requirements (`opentelemetry-sdk`, exporters, `prometheus_client`).
2. Implement instrumentation behind `TELEMETRY_ENABLED` flag.
3. Deploy to staging; verify dashboards (Grafana, New Relic) show new signals.
4. Gradually enable sampling in production and adjust alert thresholds with SRE.

## Risks & Mitigations
- **High cardinality metrics**: enforce hashing or bucketing, monitor Prometheus storage.
- **Performance overhead**: use asynchronous exporters, tune sampling rate.
- **Telemetry outages**: fail gracefully (log warning, don’t crash worker).
