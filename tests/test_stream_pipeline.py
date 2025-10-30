import json

import pytest
from fakeredis.aioredis import FakeRedis

from sploot_media_clustering.config import get_settings
from sploot_media_clustering.services.clustering import ClusterService
from workers import run_worker


@pytest.mark.asyncio
async def test_enqueue_job_publishes_payload():
    redis = FakeRedis(decode_responses=True)
    service = ClusterService(redis)
    settings = get_settings()

    try:
        await service.ensure_consumer_group()
        await service.enqueue_job("pet-001", {"payload": {"image_ids": ["img-1"], "labels": ["Portrait"]}})

        entries = await redis.xrange(settings.cluster_stream_key, count=1)
        assert entries, "expected redis stream to contain a message"

        _, fields = entries[0]
        payload = json.loads(fields["payload"])
        assert payload["pet_id"] == "pet-001"
        job_payload = payload["payload"]
        assert job_payload["payload"]["image_ids"] == ["img-1"]
        assert payload["attempts"] == 0
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_worker_handles_stream_job_and_persists_state():
    redis = FakeRedis(decode_responses=True)
    service = ClusterService(redis)
    settings = get_settings()

    original_service = run_worker.cluster_service
    run_worker.cluster_service = service
    try:
        await service.ensure_consumer_group()
        await service.enqueue_job(
            "pet-xyz",
            {
                "payload": {"image_ids": ["img-a", "img-b"], "labels": ["Portraits", "Action"], "coverage": {"portrait": 0.7}},
                "reason": "automated-test",
            },
        )

        response = await redis.xreadgroup(
            groupname=settings.cluster_consumer_group,
            consumername=settings.cluster_worker_consumer_name,
            streams={settings.cluster_stream_key: ">"},
            count=1,
            block=100,
        )
        assert response, "expected worker to read at least one message"

        _, messages = response[0]
        message_id, payload = messages[0]

        await run_worker.handle_job(redis, message_id, payload)

        pending_info = await redis.xpending(settings.cluster_stream_key, settings.cluster_consumer_group)
        assert pending_info["pending"] == 0

        state = await service.get_cluster_state("pet-xyz")
        assert state is not None
        assert state.pet_id == "pet-xyz"
        assert len(state.clusters) == 2
    finally:
        run_worker.cluster_service = original_service
        await redis.aclose()