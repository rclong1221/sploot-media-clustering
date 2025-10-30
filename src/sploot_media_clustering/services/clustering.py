from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis import ResponseError
from redis.asyncio import Redis

from ..config import get_settings
from ..infrastructure.redis import get_redis_client


@dataclass(slots=True)
class ClusterState:
    pet_id: str
    clusters: list[dict[str, Any]]
    metrics: dict[str, Any]
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["updated_at"] = self.updated_at.isoformat()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClusterState":
        updated_at = datetime.fromisoformat(payload["updated_at"]) if "updated_at" in payload else datetime.now(timezone.utc)
        return cls(
            pet_id=payload["pet_id"],
            clusters=list(payload.get("clusters", [])),
            metrics=dict(payload.get("metrics", {})),
            updated_at=updated_at,
        )


class ClusterService:
    """Interface for queuing cluster jobs and managing cached cluster state."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
        self._settings = get_settings()
        self._group_ready = False

    async def ensure_consumer_group(self) -> None:
        if self._group_ready:
            return

        try:
            await self._redis.xgroup_create(
                name=self._settings.cluster_stream_key,
                groupname=self._settings.cluster_consumer_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:  # group already exists
            if "BUSYGROUP" not in str(exc):
                raise
        finally:
            self._group_ready = True

    async def enqueue_job(self, pet_id: str, job_payload: dict[str, Any]) -> None:
        await self.ensure_consumer_group()
        attempts = int(job_payload.get("attempts", 0))
        payload = {
            "job_id": job_payload.get("job_id") or uuid4().hex,
            "pet_id": pet_id,
            "payload": job_payload,
            "attempts": attempts,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._redis.xadd(
            name=self._settings.cluster_stream_key,
            fields={"payload": json.dumps(payload)},
            maxlen=self._settings.cluster_stream_maxlen,
            approximate=self._settings.cluster_stream_approximate_trim,
        )

    async def persist_cluster_state(self, state: ClusterState) -> None:
        key = f"{self._settings.namespace}:state:{state.pet_id}"
        await self._redis.setex(key, self._settings.cluster_ttl_seconds, json.dumps(state.to_dict()))

    async def get_cluster_state(self, pet_id: str) -> ClusterState | None:
        key = f"{self._settings.namespace}:state:{pet_id}"
        raw = await self._redis.get(key)
        if not raw:
            return None
        return ClusterState.from_dict(json.loads(raw))

    async def invalidate(self, pet_id: str) -> bool:
        key = f"{self._settings.namespace}:state:{pet_id}"
        deleted = await self._redis.delete(key)
        return bool(deleted)


cluster_service = ClusterService(get_redis_client())
