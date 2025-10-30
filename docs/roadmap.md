# Media Clustering Roadmap

## Epic 1 – Reliable Job Pipeline (Redis Streams)
**Objective**: Build a production-grade ingestion pipeline so clustering jobs flow reliably from Sploot Auth to the media clustering worker.

### Milestones
1. **Redis Infrastructure**
   - [x] Update local Docker Compose with AOF persistence and stream env vars.
   - [ ] Provision dev+prod Redis instances with persistence and TLS.
   - [ ] Define stream key/group conventions and secrets management.
2. **Auth-Service Producer**
   - [x] Publish image jobs via Redis Streams (feature-flagged).
   - [x] Add retry/backoff + trace metadata + HTTP fallback.
3. **Worker Consumer**
   - [x] Implement blocking `XREADGROUP` loop, retries, dead-letter handling.
   - [ ] Structured logging + Prometheus metrics.
4. **QA & Rollout**
   - [x] Integration tests with fakeredis.
   - [ ] Staging soak test, enable feature flag in production, deprecate HTTP enqueue fallback.

## Epic 2 – High-Fidelity Clustering (Embeddings)
**Objective**: Deliver accurate, low-latency clustering using an embedding-based mixture model.

### Milestones
1. **Model Selection & Eval**
   - Benchmark candidate embedders on pet dataset.
   - Choose model + fine-tuning plan.
2. **Inference Service**
   - Package model (ONNX/TorchScript), support GPU+CPU.
   - Add observability + batching logic.
3. **Clustering Engine**
   - Implement incremental mixture model + hero scoring.
   - Integrate into worker pipeline.
4. **Validation & Rollout**
   - Offline evaluation, feature flag rollout, performance tuning.

## Epic 3 – Durable Cluster Storage (Postgres)
**Objective**: Persist cluster state and hero assets for cross-service use.

### Milestones
1. **Schema & Migrations**
   - Design tables (`cluster_jobs`, `pet_clusters`, `cluster_members`, `cluster_heroes`).
   - Ship Alembic migrations.
2. **Repository Layer**
   - Implement read/write operations with transactions.
   - Add caching hooks (Redis read-through).
3. **API Endpoints**
   - Internal routes for latest + historical clusters, job status.
   - Auth-service integration (latest version pointer).
4. **Backfill & Rollout**
   - Backfill existing pets, add cleanup cron, production rollout with monitoring.

## Epic 4 – Observability & Operations (Tracing/Metrics)
**Objective**: End-to-end visibility across auth-service, Redis, clustering worker, and persistence.

### Milestones
1. **Telemetry Foundation**
   - Integrate OpenTelemetry + Prometheus client libs.
   - Configure dev collector + dashboards.
2. **Service Instrumentation**
   - Trace spans in auth-service, worker stages, API routes.
   - Emit key metrics (job counts, latencies, retries).
3. **Logging & Alerts**
   - Structured logs with trace context.
   - Coordinate alert rules with SRE.
4. **Prod Rollout**
   - Gradual sampling enablement, performance validation, documentation.
