"""Public API routes for frontend consumption."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..services.clustering import ClusterState, cluster_service

router = APIRouter()


def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> str:
    """Verify API key from request header.
    
    In production, this would validate against a database of API keys.
    For now, we accept any key that matches the configured token.
    """
    settings = get_settings()
    if not x_api_key or x_api_key != settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return x_api_key


class ClusterMember(BaseModel):
    """A single image within a cluster."""
    image_id: str
    score: float
    position: int
    quality_score: float | None = Field(default=None, alias="qualityScore")


class Cluster(BaseModel):
    """A cluster of similar images."""
    id: str
    label: str
    hero_image_id: str | None = None
    members: list[ClusterMember]


class ClusterMetrics(BaseModel):
    """Clustering quality metrics."""
    num_clusters: int = 0
    num_images: int = 0
    avg_quality: float = 0.0
    processed_at: str | None = None


class ClusterStateResponse(BaseModel):
    """Complete clustering state for a pet."""
    pet_id: str
    clusters: list[Cluster]
    metrics: ClusterMetrics
    updated_at: str

    @classmethod
    def from_domain(cls, state: ClusterState) -> "ClusterStateResponse":
        """Convert domain model to API response."""
        clusters = [
            Cluster(
                id=str(cluster.get("id")),
                label=str(cluster.get("label", "Portraits")),
                hero_image_id=cluster.get("hero_image_id"),
                members=[
                    ClusterMember(
                        image_id=str(member.get("image_id")),
                        score=float(member.get("score", 0.0)),
                        position=int(member.get("position", idx)),
                        quality_score=float(member.get("quality_score", member.get("score", 0.0)))
                    )
                    for idx, member in enumerate(cluster.get("members", []))
                ],
            )
            for cluster in state.clusters
        ]
        
        metrics = ClusterMetrics(
            num_clusters=state.metrics.get("num_clusters", len(clusters)),
            num_images=state.metrics.get("num_images", 0),
            avg_quality=state.metrics.get("avg_quality", 0.0),
            processed_at=state.metrics.get("processed_at"),
        )
        
        return cls(
            pet_id=state.pet_id,
            clusters=clusters,
            metrics=metrics,
            updated_at=state.updated_at.isoformat()
        )


@router.get("/pets/{pet_id}/clusters", response_model=ClusterStateResponse)
async def get_pet_clusters(
    pet_id: str,
    _: Annotated[str, Depends(verify_api_key)]
) -> ClusterStateResponse:
    """Get clustering results for a specific pet.
    
    Returns all clusters with their hero images and members, along with
    quality metrics about the clustering process.
    
    Args:
        pet_id: The pet identifier
        
    Returns:
        Clustering state with all clusters and metrics
        
    Raises:
        404: No clustering results found for this pet
        401: Invalid or missing API key
    """
    state = await cluster_service.get_cluster_state(pet_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No clustering results found for pet {pet_id}"
        )
    return ClusterStateResponse.from_domain(state)


@router.get("/pets/{pet_id}/hero-images", response_model=dict[str, str])
async def get_pet_hero_images(
    pet_id: str,
    _: Annotated[str, Depends(verify_api_key)]
) -> dict[str, str]:
    """Get just the hero images from each cluster.
    
    Useful for quickly displaying representative images without
    loading full cluster data.
    
    Args:
        pet_id: The pet identifier
        
    Returns:
        Dictionary mapping cluster IDs to hero image IDs
        
    Raises:
        404: No clustering results found for this pet
        401: Invalid or missing API key
    """
    state = await cluster_service.get_cluster_state(pet_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No clustering results found for pet {pet_id}"
        )
    
    hero_images = {
        cluster.get("id"): cluster.get("hero_image_id")
        for cluster in state.clusters
        if cluster.get("hero_image_id")
    }
    
    return hero_images
