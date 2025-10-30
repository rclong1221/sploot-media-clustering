from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..infrastructure.redis import redis_alive
from ..services.clustering import ClusterState, cluster_service

router = APIRouter()


def verify_internal_token(token: Annotated[str | None, Header(alias="X-Internal-Token")]) -> str:
    settings = get_settings()
    if token != settings.internal_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid internal token")
    return token


class ClusterJobRequest(BaseModel):
    pet_id: str = Field(..., examples=["pet_123"])
    job_id: str | None = Field(None, examples=["job_456"])
    reason: str | None = Field(None, examples=["insights_ready"])
    force: bool = False
    payload: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class ClusterMember(BaseModel):
    image_id: str
    score: float
    position: int


class ClusterPayload(BaseModel):
    id: str
    label: str
    members: list[ClusterMember]
    hero_image_id: str | None = None


class ClusterMetrics(BaseModel):
    coverage: dict[str, float] = Field(default_factory=dict)
    quality_score: float | None = None
    processed_at: str | None = None


class ClusterStateResponse(BaseModel):
    pet_id: str
    clusters: list[ClusterPayload]
    metrics: ClusterMetrics
    updated_at: str

    @classmethod
    def from_domain(cls, state: ClusterState) -> "ClusterStateResponse":
        clusters = [
            ClusterPayload(
                id=str(cluster.get("id")),
                label=str(cluster.get("label", "")),
                members=[
                    ClusterMember(
                        image_id=str(member.get("image_id")),
                        score=float(member.get("score", 0.0)),
                        position=int(member.get("position", idx)),
                    )
                    for idx, member in enumerate(cluster.get("members", []))
                ],
                hero_image_id=cluster.get("hero_image_id"),
            )
            for cluster in state.clusters
        ]
        metrics = ClusterMetrics(
            **{k: v for k, v in state.metrics.items() if k in {"coverage", "quality_score", "processed_at"}}
        )
        return cls(pet_id=state.pet_id, clusters=clusters, metrics=metrics, updated_at=state.updated_at.isoformat())


@router.post("/cluster-jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_cluster_job(job: ClusterJobRequest, _: Annotated[str, Depends(verify_internal_token)]) -> dict[str, str]:
    await cluster_service.enqueue_job(job.pet_id, job.model_dump())
    return {"status": "accepted"}


@router.get("/pets/{pet_id}/clusters", response_model=ClusterStateResponse)
async def get_clusters(pet_id: str, _: Annotated[str, Depends(verify_internal_token)]) -> ClusterStateResponse:
    state = await cluster_service.get_cluster_state(pet_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cluster state not found")
    return ClusterStateResponse.from_domain(state)


@router.post("/pets/{pet_id}/invalidate", status_code=status.HTTP_202_ACCEPTED)
async def invalidate_clusters(pet_id: str, _: Annotated[str, Depends(verify_internal_token)]) -> dict[str, str]:
    existed = await cluster_service.invalidate(pet_id)
    return {"status": "removed" if existed else "noop"}


@router.get("/health/redis", status_code=status.HTTP_200_OK)
async def redis_health(_: Annotated[str, Depends(verify_internal_token)]) -> dict[str, str]:
    if not await redis_alive():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="redis unavailable")
    return {"status": "ok"}
