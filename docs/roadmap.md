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
   - [x] Structured logging + Prometheus metrics (feeds `docs/observability-dashboards.md`).
4. **QA & Rollout**
   - [x] Integration tests with fakeredis.
   - [ ] Deploy to production, enable feature flag gradually (10% → 50% → 100%).
   - [ ] Monitor worker metrics endpoint for lag/retries during ramp.
   - [ ] Remove HTTP enqueue fallback once stable at 100%.

## Epic 2 – High-Fidelity Clustering (Embeddings)
**Objective**: Deliver accurate, low-latency clustering using an embedding-based mixture model.

### Milestones
1. **Clustering Engine**
   - [x] Implement DBSCAN-based clustering with cosine similarity.
   - [x] Hero selection by centroid proximity.
   - [x] Integrate into worker pipeline.
   - [x] Unit tests for clustering logic (4/4 passing).
2. **Inference Service**
   - [x] Vision transformer embedding model (timm/ViT).
   - [x] Storage client for fetching image bytes.
   - [x] Batch embedding inference.
   - [x] Auto GPU detection (falls back to CPU if unavailable).
3. **Integration & Validation**
   - [x] Mock storage service with synthetic images.
   - [x] End-to-end test script.
   - [ ] Docker-based e2e test (worker + storage + Redis).
   - [ ] Test with real pet images from storage.
   - [ ] Tune clustering parameters based on results.
   - [ ] Benchmark latency and quality metrics.

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
