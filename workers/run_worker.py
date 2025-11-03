import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from redis import ResponseError
from redis.asyncio import Redis

from sploot_media_clustering.config import get_settings
from sploot_media_clustering.infrastructure.redis import get_redis_client
from sploot_media_clustering.services.clustering import ClusterState, cluster_service
from sploot_media_clustering.services.clustering_engine import ClusteringEngine
from sploot_media_clustering.services.storage import get_storage_client


DEFAULT_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - simple convenience override
        # Preserve standard logging metadata and merge any extra fields.
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception info if present.
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # Merge custom extras while avoiding built-in attributes.
        for key, value in record.__dict__.items():
            if key not in DEFAULT_RECORD_FIELDS and key not in payload:
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("sploot-media-clustering-worker")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = configure_logging()


JOB_RESULT_COUNTER = Counter(
    "media_cluster_jobs_processed_total",
    "Count of media clustering jobs processed by result",
    labelnames=("result",),
)

JOB_LATENCY_SECONDS = Histogram(
    "media_cluster_job_processing_seconds",
    "Time spent processing a media clustering job",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),
)

STREAM_PENDING_GAUGE = Gauge(
    "media_cluster_pending_jobs",
    "Number of jobs currently pending in the Redis consumer group",
)

STREAM_LAG_GAUGE = Gauge(
    "media_cluster_stream_lag_seconds",
    "Approximate idle time in seconds for the oldest pending job",
)


async def ensure_group(redis: Redis) -> None:
    await cluster_service.ensure_consumer_group()


async def _retry_or_deadletter(
    redis: Redis,
    job_envelope: dict[str, Any],
    message_id: str,
    error: Exception,
) -> None:
    settings = get_settings()
    attempts = int(job_envelope.get("attempts", 0)) + 1
    job_envelope["attempts"] = attempts
    await redis.xack(settings.cluster_stream_key, settings.cluster_consumer_group, message_id)

    if attempts >= settings.cluster_max_attempts:
        logger.error(
            "job moved to dead-letter stream",
            extra={
                "job_id": job_envelope.get("job_id"),
                "pet_id": job_envelope.get("pet_id"),
                "attempts": attempts,
            },
        )
        await redis.xadd(
            name=settings.cluster_dead_letter_stream,
            fields={"payload": json.dumps(job_envelope), "error": str(error)},
            maxlen=settings.cluster_stream_maxlen,
            approximate=settings.cluster_stream_approximate_trim,
        )
        JOB_RESULT_COUNTER.labels(result="dead_letter").inc()
        return

    logger.warning(
        "retrying job",
        extra={"job_id": job_envelope.get("job_id"), "pet_id": job_envelope.get("pet_id"), "attempts": attempts},
    )
    JOB_RESULT_COUNTER.labels(result="retry").inc()
    await redis.xadd(
        name=settings.cluster_stream_key,
        fields={"payload": json.dumps(job_envelope)},
        maxlen=settings.cluster_stream_maxlen,
        approximate=settings.cluster_stream_approximate_trim,
    )


async def handle_job(redis: Redis, message_id: str, payload: dict[str, str]) -> None:
    settings = get_settings()
    start_time = time.monotonic()
    try:
        job_envelope = json.loads(payload["payload"])
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("invalid job payload", extra={"error": str(exc)})
        await redis.xack(settings.cluster_stream_key, settings.cluster_consumer_group, message_id)
        JOB_RESULT_COUNTER.labels(result="invalid").inc()
        return

    pet_id = job_envelope.get("pet_id")
    job_id = job_envelope.get("job_id")
    job_payload = job_envelope.get("payload", {})
    logger.info(
        "processing cluster job",
        extra={"pet_id": pet_id, "job_id": job_id, "reason": job_payload.get("reason")},
    )

    # Fetch ALL images with embeddings for this pet (not just the newly uploaded ones)
    storage = get_storage_client()
    logger.info("fetching all images with embeddings for pet", extra={
        "pet_id": pet_id,
        "job_id": job_id,
    })
    
    try:
        image_ids = await storage.fetch_pet_images_with_embeddings(int(pet_id))
    except Exception as fetch_err:
        logger.error("failed to fetch pet images", extra={
            "pet_id": pet_id,
            "job_id": job_id,
            "error_type": type(fetch_err).__name__,
            "error_msg": str(fetch_err)
        })
        raise
    
    if not image_ids:
        logger.warning("no images with embeddings found for pet", extra={"pet_id": pet_id, "job_id": job_id})
        await redis.xack(settings.cluster_stream_key, settings.cluster_consumer_group, message_id)
        JOB_RESULT_COUNTER.labels(result="skipped").inc()
        return

    logger.info("found images with embeddings", extra={
        "pet_id": pet_id,
        "job_id": job_id,
        "image_count": len(image_ids),
    })
    
    # Fetch embeddings for all images from database (generated by embedder service)
    logger.info(
        "fetching embeddings from database",
        extra={"pet_id": pet_id, "count": len(image_ids)},
    )
    
    insights_data = await storage.fetch_insights_batch(image_ids)
    
    # Extract embeddings and filter to images that have them
    embeddings_map = {}
    for img_id_str, insight in insights_data.items():
        if insight and insight.get("has_embedding") and insight.get("embedding"):
            embeddings_map[img_id_str] = insight["embedding"]
    
    # Filter to only images with embeddings
    valid_ids = [img_id for img_id in image_ids if img_id in embeddings_map]
    embeddings_list = [embeddings_map[img_id] for img_id in valid_ids]
    
    if not valid_ids:
        logger.warning(
            "no embeddings found for any images",
            extra={"pet_id": pet_id, "job_id": job_id, "total_images": len(image_ids)},
        )
        return
    
    # Convert embeddings list to numpy array for clustering
    embeddings = np.array(embeddings_list)
    
    logger.info(
        "fetched embeddings from database",
        extra={
            "pet_id": pet_id,
            "total_images": len(image_ids),
            "with_embeddings": len(valid_ids),
            "embedding_shape": embeddings.shape,
        },
    )

    # Run clustering with identity separation enabled
    # Uses tighter epsilon (0.15) to separate different individual pets
    engine = ClusteringEngine(
        eps=settings.clustering_eps,
        min_samples=settings.clustering_min_samples,
        max_cluster_size=settings.max_cluster_size,
        identity_eps=0.15,  # Tighter threshold for pet identity
    )
    cluster_results = engine.cluster_images(valid_ids, embeddings, use_identity_clustering=True)

    clusters: list[dict[str, Any]] = []
    insight_updates: list[dict[str, Any]] = []

    for result in cluster_results:
        cluster_identifier = f"{pet_id}-{result.cluster_id}"
        members_payload: list[dict[str, Any]] = []

        for member in result.members:
            member_score = float(member.score)
            members_payload.append(
                {
                    "image_id": member.image_id,
                    "score": member_score,
                    "position": member.position,
                    "quality_score": member_score,
                }
            )

            insight_updates.append(
                {
                    "source_image_id": int(member.image_id),
                    "quality_score": member_score,
                    "processor_version": "v1.0.0",
                    "tags": {
                        "cluster": {
                            "id": cluster_identifier,
                            "label": result.label,
                            "position": member.position,
                            "score": member_score,
                            "is_hero": member.image_id == result.hero_image_id,
                        }
                    },
                }
            )

        clusters.append(
            {
                "id": cluster_identifier,
                "label": result.label,
                "hero_image_id": result.hero_image_id,
                "members": members_payload,
                "quality_score": result.quality_score,
            }
        )

    metrics = {
        "num_clusters": len(clusters),
        "num_images": len(image_ids),
        "avg_quality": float(np.mean([r.quality_score for r in cluster_results])) if cluster_results else 0.0,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    cluster_state = ClusterState(pet_id=str(pet_id), clusters=clusters, metrics=metrics)
    await cluster_service.persist_cluster_state(cluster_state)

    if insight_updates:
        try:
            await storage.store_insights_batch(insight_updates)
            logger.info(
                "updated insight quality scores",
                extra={"pet_id": pet_id, "count": len(insight_updates)},
            )
        except Exception as update_err:
            logger.warning(
                "failed to update insight quality",
                extra={
                    "pet_id": pet_id,
                    "error": str(update_err),
                    "error_type": type(update_err).__name__,
                },
            )

    await redis.xack(settings.cluster_stream_key, settings.cluster_consumer_group, message_id)
    logger.info(
        "cluster state updated",
        extra={"pet_id": pet_id, "num_clusters": len(clusters), "num_images": len(image_ids)},
    )
    JOB_RESULT_COUNTER.labels(result="success").inc()
    JOB_LATENCY_SECONDS.observe(time.monotonic() - start_time)


async def consume_jobs(redis: Redis) -> None:
    settings = get_settings()
    await ensure_group(redis)
    while True:
        streams = {settings.cluster_stream_key: ">"}
        response = await redis.xreadgroup(
            groupname=settings.cluster_consumer_group,
            consumername=settings.cluster_worker_consumer_name,
            streams=streams,
            count=settings.cluster_read_count,
            block=settings.cluster_read_timeout_ms,
        )
        if not response:
            continue

        for _, messages in response:
            for message_id, payload in messages:
                try:
                    await handle_job(redis, message_id, payload)
                except Exception as exc:
                    try:
                        job_envelope = json.loads(payload.get("payload", "{}"))
                    except json.JSONDecodeError:
                        job_envelope = {"payload": payload.get("payload")}
                    JOB_RESULT_COUNTER.labels(result="failure").inc()
                    logger.exception(
                        "cluster job failed",
                        extra={
                            "message_id": message_id,
                            "job_id": job_envelope.get("job_id"),
                            "pet_id": job_envelope.get("pet_id"),
                            "error": str(exc),
                        },
                    )
                    await _retry_or_deadletter(redis, job_envelope, message_id, exc)
                finally:
                    await record_stream_metrics(redis)


async def record_stream_metrics(redis: Redis) -> None:
    settings = get_settings()
    if not settings.worker_metrics_enabled:
        return
    try:
        summary = await redis.xpending(settings.cluster_stream_key, settings.cluster_consumer_group)
    except (ResponseError, TypeError, NotImplementedError):
        # Pending metrics unavailable (e.g., group missing in fakeredis before ensure). Reset gauges.
        STREAM_PENDING_GAUGE.set(0)
        STREAM_LAG_GAUGE.set(0)
        return

    if not summary:
        STREAM_PENDING_GAUGE.set(0)
        STREAM_LAG_GAUGE.set(0)
        return

    pending_count = summary.get("pending") if isinstance(summary, dict) else getattr(summary, "pending", 0)
    STREAM_PENDING_GAUGE.set(pending_count or 0)

    try:
        oldest = await redis.xpending_range(
            settings.cluster_stream_key,
            settings.cluster_consumer_group,
            min="-",
            max="+",
            count=1,
        )
    except (ResponseError, NotImplementedError):
        STREAM_LAG_GAUGE.set(0)
        return

    if oldest:
        idle_ms = oldest[0].get("idle", 0) if isinstance(oldest[0], dict) else getattr(oldest[0], "idle", 0)
        STREAM_LAG_GAUGE.set(idle_ms / 1000)
    else:
        STREAM_LAG_GAUGE.set(0)


async def main() -> None:
    redis = get_redis_client()
    settings = get_settings()

    if settings.worker_metrics_enabled:
        start_http_server(settings.worker_metrics_port, addr=settings.worker_metrics_host)
        logger.info(
            "metrics server started",
            extra={"port": settings.worker_metrics_port, "host": settings.worker_metrics_host},
        )

    await consume_jobs(redis)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("worker stopped")
