# Postgres Persistence Plan

## Goals
- Persist per-pet cluster state, hero selections, and job audit metadata in Postgres for durability and cross-service consumption.
- Provide APIs for internal services (auth-service, Pets Experience API) to query cluster data with consistent semantics.
- Support both developer environments (Docker Compose) and production deployments using managed Postgres (RDS, Cloud SQL, etc.).

## Non-Goals
- Building frontend-facing endpoints (those will be handled via existing APIs once data is stored).
- Implementing long-term analytics warehousing (Snowflake/BigQuery export is a separate project).
- Replacing Redis cache (Postgres becomes the source of truth; Redis remains a read-through cache).

## Data Model

### Tables
- `cluster_jobs`
  - `id` (UUID, primary key)
  - `pet_id` (UUID, indexed)
  - `status` (enum: queued, processing, succeeded, failed)
  - `attempts`
  - `last_error`
  - `enqueued_at`, `started_at`, `completed_at`
- `pet_clusters`
  - `id` (UUID)
  - `pet_id` (UUID, composite unique with `version`)
  - `version` (bigint, monotonic per pet)
  - `cluster_count`
  - `metrics` (JSONB: coverage, silhouette score, etc.)
  - `created_at`
- `cluster_members`
  - `cluster_id` (UUID, FK -> `pet_clusters.id`)
  - `image_id` (UUID)
  - `distance`
  - `metadata` (JSONB)
  - PK (`cluster_id`, `image_id`)
- `cluster_heroes`
  - `cluster_id` (UUID)
  - `image_id` (UUID)
  - `score`
  - `selected_at`
  - PK (`cluster_id`, `image_id`)
- `cluster_snapshots`
  - Optional historical storage; keep compressed payload for audit/rollback.

### Enums
- `cluster_job_status` (queued, processing, succeeded, failed)

### Indexing
- `pet_clusters (pet_id, created_at DESC)`
- `cluster_members (image_id)` for reverse lookups
- Partial index on `cluster_jobs (pet_id) WHERE status != 'succeeded'` for quick retry scanning.

## Migration Strategy
1. Create Alembic migrations in `sploot_media_clustering` for new tables/enums.
2. For auth-service, add migrations only if we mirror minimal metadata (e.g., linking pets to latest cluster ID).
3. Provide seed migration for dev environment with sample data.

## Application Changes
- **Worker**: After clustering, write job record + cluster snapshot inside a transaction.
- **API**: Add endpoints:
  - `GET /internal/pets/{pet_id}/clusters/latest` — returns the most recent `pet_clusters` with hero assignments.
  - `GET /internal/pets/{pet_id}/clusters/{version}` — historical view.
  - `GET /internal/pets/{pet_id}/jobs` — job status for debugging.
- **Cache**: After writing to Postgres, update Redis cache (or invalidate) to keep responses fast.
- **Auth-Service Integration**: Optionally store `latest_cluster_version` on pet records for quick joins.

## Dev vs. Prod Config

| Setting | Dev | Prod |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5433/media_clusters` | Managed Postgres with TLS |
| Pool size | 5 | 15–30 (depends on worker count) |
| Statement timeout | 30s | 15s |
| SSL mode | disable | require |

## Observability & Ops
- Metrics: job success/failure counts, write latency, Postgres pool utilization.
- Alerts: high failure rate, stale cluster versions (no updates >24h), backlog of failed jobs.
- Backups: rely on managed Postgres automated backups; document restore playbook.
- Data retention: keep cluster history for 90 days (configurable) via scheduled cleanup job.

## Testing
- Unit tests for repository layer using transaction rollbacks.
- Integration tests spinning Postgres container (`pytest-postgresql` or test fixtures).
- Load tests to simulate 10k pets and ensure queries stay <200ms.

## Rollout Plan
1. Merge migrations and repository layer behind feature flag.
2. Deploy to staging; run backfill job to populate clusters for existing pets.
3. Enable API reads from Postgres + Redis cache.
4. Monitor metrics and logs; if healthy, roll to production and deprecate stub storage.

## Open Questions
- Do we need cross-region replication for cluster data? (likely no, but confirm SLA).
- Should we expose GraphQL or REST only? (current scope sticks to REST).
- How do we handle privacy/PII? Pet images aren’t considered PII, but ensure compliance review.
