# Embedding Mixture Model Strategy

## Goals
- Deliver high-accuracy pet photo clustering by replacing the stub heuristic with an embedding-driven mixture model pipeline.
- Support near-real-time updates as new images arrive while keeping inference latency within 1s per image on CPU, <200ms with GPU acceleration.
- Produce ranked hero assets per cluster to power downstream personalization surfaces.

## Non-Goals
- Building a full recommendation engine (e.g., cross-pet or user-level suggestions).
- Persisting cluster outputs (handled by a subsequent milestone).
- Implementing UI integrations in `sploot-frontend`.

## Requirements
- **Accuracy**: ≥90% cluster purity on curated validation set; hero selection precision ≥85%.
- **Latency**: ≤1s/image on CPU-only nodes; ≤200ms/image with GPU (A10G or equivalent).
- **Scalability**: Handle 10k pets with 100 images each without re-computing from scratch.
- **Resource Footprint**: Fit embedder + clustering model in <8GB GPU memory (or <4GB CPU RAM, batched).

## Architecture Overview
1. **Feature Extraction**
   - Use a pre-trained vision-language model (e.g., `open-clip/ViT-H-14` fine-tuned on pets) for embeddings.
   - Optional lightweight fine-tuning with LoRA adapters using an internal pet dataset.
   - Embedder served via TorchScript or ONNX for portability.
2. **Clustering Core**
   - Maintain incremental clusters per pet using a mixture-of-Gaussians (MoG) or HDBSCAN with centroid caching.
   - Employ Faiss (GPU) or scikit-learn (CPU) for vector indexing.
   - Incrementally update clusters on new image ingestion; avoid reclustering entire history.
3. **Hero Selection**
   - Score images per cluster using a composite metric (quality + pose + recency).
   - Store top-N hero candidates per cluster in memory cache and enqueue for persistence layer (future milestone).
4. **Serving Layer**
   - Expose `GET /internal/pets/{pet_id}/clusters` returning cluster descriptors, hero images, and coverage metrics.
   - Cache responses in Redis with TTL, invalidated when new jobs complete.

## Data Flow
```
Image Upload -> Auth Service -> Redis Stream Job -> Worker Consumes ->
  |-> Embed (batch, GPU)
  |-> Update Cluster Model (Faiss index + MoG parameters)
  |-> Select Heroes
  |-> Emit cluster payload (Redis cache + future Postgres persistence)
```

## Components
- **Embedding Service**: Optional microservice or in-process module. Batch incoming images; support dynamic batching to maximize GPU utilization.
- **Model Registry**: Store model artifacts in S3 + version via MLflow or similar; include rollback plan.
- **Cluster Manager**: Python module handling incremental updates, hero scoring, and serialization.
- **Evaluation Suite**: Offline notebooks/tests to validate purity, hero accuracy, and drift.

## Implementation Plan
1. **Prototype**
   - Collect sample dataset (pet images with cluster labels).
   - Evaluate multiple embedders (`open-clip`, `EVA02-CLIP`, `DINOv2`, `SigLIP`); document accuracy vs. latency.
   - Select base model and fine-tuning strategy.
2. **Model Serving**
   - Convert chosen model to ONNX/TorchScript.
   - Add inference wrapper with GPU/CPU fallbacks, batching, and observability (timings, error counts).
3. **Clustering Engine**
   - Implement incremental MoG using scikit-learn or PyTorch mixture modules.
   - For GPU path, leverage Faiss indexes with IVFPQ or HNSW; maintain CPU fallback.
   - Add cluster validation (minimum cluster size, outlier handling).
4. **Hero Selection Logic**
   - Define scoring function combining embedding norm, pose classifier output, quality score, and recency weight.
   - Unit-test scoring with synthetic inputs.
5. **Integration**
   - Hook pipeline into worker job handler; ensure retries and idempotency per job.
   - Cache resulting cluster payload; emit metrics (processing latency, cluster count, hero scores).
6. **Evaluation & Tuning**
   - Build offline evaluation script comparing new clusters against ground truth.
   - Run A/B backtest on historical uploads; adjust thresholds.
7. **Deployment**
   - Package model artifacts with Docker image (or fetch from model registry at bootstrap).
   - Configure GPU-enabled deployment path (CUDA base image, drivers).
   - Add feature flag to toggle between stub and new pipeline during rollout.

## Observability
- Expose Prometheus histograms for embedding latency, clustering latency, hero scoring.
- Log structured metadata (`pet_id`, `cluster_id`, `model_version`, `latency_ms`).
- Emit tracing spans around each pipeline stage.

## Risk & Mitigation
- **Model Drift**: Schedule periodic re-evaluation; keep older model versions for rollback.
- **Resource Saturation**: Autoscale worker pods based on GPU/CPU utilization. Consider queue depth metrics for scaling triggers.
- **Quality Regressions**: Maintain human-in-the-loop review for hero selections during beta rollout.

## Deliverables
- Reusable embedding + clustering modules within `sploot_media_clustering.services`.
- Model artifacts stored in registry with version tagging.
- Integration tests covering end-to-end job processing with mocked embeddings.
- Deployment runbook including GPU provisioning steps and rollback instructions.
