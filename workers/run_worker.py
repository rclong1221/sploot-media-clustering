import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from sploot_media_clustering.config import get_settings
from sploot_media_clustering.infrastructure.redis import get_redis_client
from sploot_media_clustering.services.clustering import ClusterState, cluster_service

logger = logging.getLogger("sploot-media-clustering-worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


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
            extra={"job_id": job_envelope.get("job_id"), "pet_id": job_envelope.get("pet_id"), "attempts": attempts},
        )
        await redis.xadd(
            name=settings.cluster_dead_letter_stream,
            fields={"payload": json.dumps(job_envelope), "error": str(error)},
            maxlen=settings.cluster_stream_maxlen,
            approximate=settings.cluster_stream_approximate_trim,
        )
        return

    logger.warning(
        "retrying job",
        extra={"job_id": job_envelope.get("job_id"), "pet_id": job_envelope.get("pet_id"), "attempts": attempts},
    )
    await redis.xadd(
        name=settings.cluster_stream_key,
        fields={"payload": json.dumps(job_envelope)},
        maxlen=settings.cluster_stream_maxlen,
        approximate=settings.cluster_stream_approximate_trim,
    )


async def handle_job(redis: Redis, message_id: str, payload: dict[str, str]) -> None:
    settings = get_settings()
    try:
        job_envelope = json.loads(payload["payload"])
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("invalid job payload", extra={"error": str(exc)})
        await redis.xack(settings.cluster_stream_key, settings.cluster_consumer_group, message_id)
        return

    pet_id = job_envelope.get("pet_id")
    job_id = job_envelope.get("job_id")
    job_payload = job_envelope.get("payload", {})
    logger.info(
        "processing cluster job",
        extra={"pet_id": pet_id, "job_id": job_id, "reason": job_payload.get("reason")},
    )

    image_ids = job_payload.get("image_ids") or ["placeholder-image"]
    labels = job_payload.get("labels") or ["Portraits", "Action Shots"]
    clusters = [
        {
            "id": f"{pet_id}-cluster-{idx}",
            "label": label,
            "hero_image_id": random.choice(image_ids),
            "members": [
                {"image_id": image_id, "score": round(random.random(), 3), "position": pos}
                for pos, image_id in enumerate(image_ids)
            ],
        }
        for idx, label in enumerate(labels)
    ]

    metrics = {
        "coverage": job_payload.get("coverage", {"portrait": 0.6, "action": 0.4}),
        "quality_score": job_payload.get("quality_score", round(random.uniform(0.6, 0.95), 3)),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    cluster_state = ClusterState(pet_id=str(pet_id), clusters=clusters, metrics=metrics)
    await cluster_service.persist_cluster_state(cluster_state)
    await redis.xack(settings.cluster_stream_key, settings.cluster_consumer_group, message_id)
    logger.info("cluster state updated", extra={"pet_id": pet_id, "clusters": len(clusters)})


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


async def main() -> None:
    redis = get_redis_client()
    await consume_jobs(redis)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("worker stopped")
