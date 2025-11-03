# Sploot Media Clustering Service

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.2-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7.4-DC382D.svg?logo=redis&logoColor=white)](https://redis.io)

The Sploot Media Clustering Service is an internal microservice that ingests structured photo insights and maintains per-pet image clusters that power the Pets Page and downstream recommendation surfaces. It provides a secure FastAPI-based HTTP interface for trusted internal callers while delegating computationally intensive clustering work to asynchronous workers that consume jobs from Redis Streams.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Docker Compose](#docker-compose)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

## Overview

The Sploot Media Clustering Service is responsible for:

- **Job Ingestion**: Consuming `media.cluster` jobs emitted after photo insight extraction via Redis Streams
- **Clustering Logic**: Aggregating pose, context, and quality vectors per pet to maintain cluster centroids
- **Hero Selection**: Identifying representative hero images for each cluster based on quality scores
- **State Management**: Caching cluster states in Redis with configurable TTL for fast retrieval
- **Internal API**: Serving cluster data to internal services through authenticated HTTP endpoints
- **Reliability**: Implementing retry logic and dead-letter queues for failed job processing

This service is designed for **internal use only** and requires authentication via shared tokens (`X-Internal-Token` header).

## Features

- ✅ **Asynchronous Architecture**: FastAPI + async Redis for high-throughput, non-blocking operations
- ✅ **Worker Pattern**: Dedicated consumer workers for background cluster computation
- ✅ **Redis Streams**: Durable message queue with consumer groups for reliable job processing
- ✅ **Automatic Retries**: Failed jobs are retried up to 5 times before moving to dead-letter stream
- ✅ **State Caching**: Cluster results cached in Redis with configurable TTL (default 24 hours)
- ✅ **Health Checks**: Built-in endpoints for service and Redis health monitoring
- ✅ **Token-Based Auth**: Simple but effective internal authentication via shared secrets
- ✅ **Extensible Design**: Pluggable clustering algorithms and persistence adapters
- ✅ **Docker Ready**: Production-ready Dockerfile and Docker Compose setup

## Architecture

```
┌─────────────────┐
│  Internal APIs  │
│  (Auth Service) │
└────────┬────────┘
         │ POST /internal/cluster-jobs
         ▼
┌─────────────────────────────────────┐
│   Sploot Media Clustering API       │
│   (FastAPI + Uvicorn)               │
│   - Token Authentication            │
│   - Job Submission                  │
│   - State Retrieval                 │
└──────────┬──────────────────────────┘
           │ writes to
           ▼
    ┌──────────────┐
    │ Redis Streams│  ◄───────┐
    │ (Job Queue)  │          │
    └──────┬───────┘          │
           │                  │ retry
           │ consumes         │
           ▼                  │
┌──────────────────────┐     │
│  Clustering Workers  │─────┘
│  (Async Consumers)   │
│  - Process images    │
│  - Compute clusters  │
│  - Store results     │
└──────────┬───────────┘
           │ writes to
           ▼
    ┌──────────────┐
    │ Redis Cache  │
    │ (Cluster TTL)│
    └──────────────┘
```

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Runtime** | Python | 3.11 |
| **Web Framework** | FastAPI | 0.115.2 |
| **ASGI Server** | Uvicorn | 0.30.6 |
| **Message Queue** | Redis Streams | 7.4 |
| **Redis Client** | redis-py | 5.1.1 |
| **Data Science** | NumPy, scikit-learn | 2.1.2, 1.5.2 |
| **Config Management** | Pydantic Settings | 2.6.0 |
| **Testing** | pytest, pytest-asyncio | 8.3.3, 0.24.0 |
| **Mocking** | fakeredis | 2.21.3 |

## Project Structure

```
sploot_media_clustering/
├── README.md                          # This file
├── Dockerfile                         # Production container image
├── docker-compose.local.yml           # Local development stack
├── pytest.ini                         # Pytest configuration
├── requirements.txt                   # Python dependencies
├── docs/                              # Additional documentation
│   ├── embedding-mixture-model.md     # Clustering algorithm design
│   ├── postgres-persistence.md        # Future persistence layer
│   ├── redis-streams-ingestion.md     # Stream processing details
│   ├── roadmap.md                     # Project roadmap
│   └── tracing-metrics.md             # Observability setup
├── src/
│   └── sploot_media_clustering/
│       ├── __init__.py
│       ├── app.py                     # FastAPI application factory
│       ├── config.py                  # Pydantic settings
│       ├── infrastructure/
│       │   └── redis.py               # Redis client singleton
│       ├── routes/
│       │   ├── __init__.py
│       │   └── internal.py            # Internal API endpoints
│       └── services/
│           ├── __init__.py
│           └── clustering.py          # Clustering service & state
├── tests/
│   ├── conftest.py                    # Pytest fixtures
│   └── test_stream_pipeline.py        # Integration tests
└── workers/
    ├── __init__.py
    └── run_worker.py                  # Consumer worker entrypoint
```

## Getting Started

### Prerequisites

- **Python 3.11+** (for local development)
- **Redis 7.4+** (or use Docker Compose)
- **Docker & Docker Compose** (optional, for containerized setup)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/rclong1221/sploot-media-clustering.git
   cd sploot-media-clustering
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Set up environment variables** (optional `.env` file)
   ```bash
   cat > .env << EOF
   REDIS_URL=redis://127.0.0.1:6379/0
   INTERNAL_TOKEN=super-secret-token
   CLUSTER_STREAM_KEY=streams:media.cluster
   CLUSTER_CONSUMER_GROUP=media-clustering-workers
   CLUSTER_WORKER_CONSUMER_NAME=media-clustering-worker-1
   CLUSTER_TTL_SECONDS=86400
   EOF
   ```

5. **Start Redis** (if not using Docker)
   ```bash
   redis-server
   ```

6. **Run the API server**
   ```bash
   uvicorn sploot_media_clustering.app:create_app --factory --reload --port 9007
   ```

   The API will be available at `http://localhost:9007`

7. **Run the worker** (in a separate terminal)
   ```bash
   source .venv/bin/activate
   python workers/run_worker.py
   ```

8. **Test the health endpoint**
   ```bash
   curl http://localhost:9007/healthz
   # {"status":"ok"}
   ```

### Docker Compose

The easiest way to run the complete stack (Redis + API + Worker):

```bash
docker compose -f docker-compose.local.yml up --build
```

This will start:
- **Redis 7.4** on port `6379`
- **API server** on port `9007`
- **Background worker** consuming from Redis Streams
- **Prometheus metrics** from the worker on port `9105`

To seed load during staging rehearsals, use `scripts/replay_staging_traffic.py` with the sample payloads under `docs/examples`.

To stop:
```bash
docker compose -f docker-compose.local.yml down
```

To remove volumes:
```bash
docker compose -f docker-compose.local.yml down -v
```

## Configuration

All configuration is managed via environment variables using Pydantic Settings. Create a `.env` file or export variables directly.

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `local` | Environment: `local`, `development`, `staging`, `production` |
| `APP_NAME` | `sploot-media-clustering` | Service name for logging |
| `INTERNAL_TOKEN` | `changeme` | **Required** - Shared secret for internal auth |

### Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis connection URL |
| `REDIS_USERNAME` | `None` | Redis username (if auth required) |
| `REDIS_PASSWORD` | `None` | Redis password (if auth required) |
| `REDIS_SSL` | `false` | Enable SSL/TLS for Redis |
| `REDIS_SSL_CA_CERTS` | `None` | Path to CA certs for SSL verification |
| `REDIS_POOL_MAX_CONNECTIONS` | `20` | Max connections in pool |
| `REDIS_SOCKET_TIMEOUT` | `None` | Socket timeout in seconds |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | `5.0` | Connection timeout in seconds |
| `REDIS_HEALTHCHECK_INTERVAL` | `30` | Health check interval in seconds |
| `REDIS_RETRY_ON_TIMEOUT` | `true` | Retry on timeout errors |

### Clustering Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `NAMESPACE` | `sploot.media.clusters` | Redis key namespace |
| `CLUSTER_TTL_SECONDS` | `86400` | Cache TTL for cluster state (24 hours) |
| `MAX_CLUSTER_SIZE` | `24` | Maximum images per cluster |
| `CLUSTER_STREAM_KEY` | `streams:media.cluster` | Redis Stream key for jobs |
| `CLUSTER_DEAD_LETTER_STREAM` | `streams:media.cluster.deadletter` | Dead letter stream for failed jobs |
| `CLUSTER_STREAM_MAXLEN` | `10000` | Max stream length (trimmed) |
| `CLUSTER_STREAM_APPROXIMATE_TRIM` | `true` | Use approximate trimming |
| `CLUSTER_CONSUMER_GROUP` | `media-clustering-workers` | Consumer group name |
| `CLUSTER_WORKER_CONSUMER_NAME` | `media-clustering-worker` | Worker consumer name |
| `CLUSTER_READ_TIMEOUT_MS` | `5000` | Read timeout for XREADGROUP |
| `CLUSTER_READ_COUNT` | `16` | Max messages per read |
| `CLUSTER_RETRY_IDLE_MS` | `60000` | Retry idle time for pending messages |
| `CLUSTER_MAX_ATTEMPTS` | `5` | Max retry attempts before dead-letter |

### Worker Metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_METRICS_ENABLED` | `true` | Toggle the Prometheus metrics endpoint |
| `WORKER_METRICS_HOST` | `0.0.0.0` | Interface the metrics server binds to |
| `WORKER_METRICS_PORT` | `9105` | Port exposing `/metrics` for Prometheus |

## API Reference

All internal endpoints require the `X-Internal-Token` header matching the configured `INTERNAL_TOKEN`.

### Health Check

```http
GET /healthz
```

**Response:**
```json
{
  "status": "ok"
}
```

### Submit Cluster Job

Enqueues a clustering job for a pet to be processed asynchronously by workers.

```http
POST /internal/cluster-jobs
X-Internal-Token: super-secret-token
Content-Type: application/json
```

**Request Body:**
```json
{
  "pet_id": "pet_123",
  "job_id": "job_456",
  "reason": "insights_ready",
  "force": false,
  "payload": {
    "image_ids": ["img_001", "img_002", "img_003"],
    "labels": ["Portraits", "Action Shots"],
    "coverage": {
      "portrait": 0.6,
      "action": 0.4
    },
    "quality_score": 0.85
  },
  "metadata": {
    "triggered_by": "insight-service"
  }
}
```

**Response:** `202 Accepted`
```json
{
  "status": "accepted"
}
```

### Get Pet Clusters

Retrieves the current cluster state for a pet from the cache.

```http
GET /internal/pets/{pet_id}/clusters
X-Internal-Token: super-secret-token
```

**Response:** `200 OK`
```json
{
  "pet_id": "pet_123",
  "clusters": [
    {
      "id": "pet_123-cluster-0",
      "label": "Portraits",
      "hero_image_id": "img_001",
      "members": [
        {
          "image_id": "img_001",
          "score": 0.95,
          "position": 0
        },
        {
          "image_id": "img_002",
          "score": 0.87,
          "position": 1
        }
      ]
    }
  ],
  "metrics": {
    "coverage": {
      "portrait": 0.6,
      "action": 0.4
    },
    "quality_score": 0.85,
    "processed_at": "2025-10-30T12:34:56.789Z"
  },
  "updated_at": "2025-10-30T12:34:56.789Z"
}
```

**Error:** `404 Not Found` if cluster state doesn't exist or has expired.

### Invalidate Pet Clusters

Forces invalidation of cached cluster state for a pet.

```http
POST /internal/pets/{pet_id}/invalidate
X-Internal-Token: super-secret-token
```

**Response:** `202 Accepted`
```json
{
  "status": "removed"  // or "noop" if nothing to invalidate
}
```

### Redis Health Check

Verifies Redis connectivity.

```http
GET /internal/health/redis
X-Internal-Token: super-secret-token
```

**Response:** `200 OK` or `503 Service Unavailable`

## Testing

Run the test suite using pytest:

```bash
# Activate the virtualenv if you have not already
source .venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=src/sploot_media_clustering --cov-report=html

# Run the Redis Streams integration tests backed by fakeredis
pytest tests/test_stream_pipeline.py

# Run with verbose output
pytest -v
```

The Redis Streams pipeline tests in `tests/test_stream_pipeline.py` rely on `fakeredis`, so they run entirely in memory without requiring a live Redis instance.

## Deployment

### Building the Docker Image

```bash
docker build -t sploot-media-clustering:latest .
```

### Running the Container

**API Server:**
```bash
docker run --rm \
  -p 9007:9007 \
  -e REDIS_URL=redis://your-redis-host:6379/0 \
  -e INTERNAL_TOKEN=your-secret-token \
  sploot-media-clustering:latest
```

**Worker:**
```bash
docker run --rm \
  -e REDIS_URL=redis://your-redis-host:6379/0 \
  -e INTERNAL_TOKEN=your-secret-token \
  sploot-media-clustering:latest \
  python workers/run_worker.py
```

### Environment-Specific Deployment

1. **Staging/Production**: Use managed Redis (AWS ElastiCache, Azure Cache for Redis, etc.)
2. **Configure SSL**: Set `REDIS_SSL=true` and provide certificate paths if required
3. **Scaling Workers**: Run multiple worker containers with unique `CLUSTER_WORKER_CONSUMER_NAME` values
4. **Monitoring**: Integrate with your observability stack (see `docs/tracing-metrics.md`)
5. **Secrets Management**: Use secret managers (AWS Secrets Manager, HashiCorp Vault) for `INTERNAL_TOKEN`

## Documentation

Additional documentation is available in the `docs/` directory:

- **[embedding-mixture-model.md](docs/embedding-mixture-model.md)** - Future embedding-based clustering algorithm design
- **[postgres-persistence.md](docs/postgres-persistence.md)** - Plans for persistent storage layer
- **[redis-streams-ingestion.md](docs/redis-streams-ingestion.md)** - Deep dive into Redis Streams architecture
- **[roadmap.md](docs/roadmap.md)** - Project roadmap and upcoming features
- **[staging-soak-rehearsal.md](docs/staging-soak-rehearsal.md)** - Checklist and schedule for the staging soak rehearsal
- **[observability-dashboards.md](docs/observability-dashboards.md)** - Metrics, dashboards, and alert policies
- **dashboards/media-clustering-redis-streams.json** - Grafana dashboard definition for Redis Streams metrics
- **scripts/deploy-dashboards.sh** - Helper to publish dashboards via the Grafana API
- **scripts/replay_staging_traffic.py** - Traffic replay utility for staging soak tests
- **[tracing-metrics.md](docs/tracing-metrics.md)** - Observability, tracing, and metrics integration

## Roadmap

### Current (MVP)
- ✅ Redis Streams job ingestion
- ✅ Basic clustering logic (stub implementation)
- ✅ FastAPI internal endpoints
- ✅ Worker consumer pattern
- ✅ Retry/dead-letter handling

### Near-Term
- [ ] Replace stub clustering with embedding-based mixture model
- [ ] Add Postgres persistence layer for cluster history
- [ ] Implement proper hero image selection algorithm
- [ ] Add comprehensive integration tests
- [ ] OpenTelemetry tracing integration

### Future
- [ ] Support for incremental cluster updates
- [ ] ML model versioning and A/B testing
- [ ] Real-time cluster quality metrics dashboard
- [ ] Cross-pet similarity recommendations
- [ ] BullMQ/RabbitMQ adapter options

See [docs/roadmap.md](docs/roadmap.md) for detailed planning.

## Contributing

This is an internal Sploot project. For contribution guidelines:

1. Create a feature branch from `main`
2. Follow existing code style (Black, isort, mypy)
3. Add tests for new functionality
4. Update documentation as needed
5. Submit a pull request with clear description

### Code Quality

```bash
# Format code
black src/ tests/ workers/

# Sort imports
isort src/ tests/ workers/

# Type checking
mypy src/ workers/

# Linting
ruff check src/ tests/ workers/
```

---

**Maintainer**: [rclong1221](https://github.com/rclong1221)  
**Repository**: [sploot-media-clustering](https://github.com/rclong1221/sploot-media-clustering)  
**License**: Internal Sploot Project
