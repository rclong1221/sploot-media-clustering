"""Clustering engine using embedding-based similarity and mixture models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import pairwise_distances


@dataclass
class ClusterResult:
    """Represents a single cluster with members and hero image."""

    cluster_id: str
    label: str
    hero_image_id: str
    members: list[ClusterMember]
    quality_score: float


@dataclass
class ClusterMember:
    """Individual image within a cluster."""

    image_id: str
    score: float
    position: int


class ClusteringEngine:
    """Produces image clusters from embeddings using density-based clustering."""

    def __init__(
        self,
        eps: float = 0.3,
        min_samples: int = 2,
        max_cluster_size: int = 24,
        identity_eps: float | None = None,
    ) -> None:
        self.eps = eps
        self.min_samples = min_samples
        self.max_cluster_size = max_cluster_size
        # Identity epsilon for pet separation (tighter threshold)
        self.identity_eps = identity_eps if identity_eps is not None else eps * 0.5

    def cluster_images(
        self,
        image_ids: list[str],
        embeddings: np.ndarray,
        use_identity_clustering: bool = True,
    ) -> list[ClusterResult]:
        """
        Cluster images by embedding similarity.
        
        Args:
            image_ids: List of image identifiers
            embeddings: Normalized embedding vectors (N × D)
            use_identity_clustering: If True, uses tighter eps for pet identity separation
            
        Returns:
            List of ClusterResult objects
        """
        if len(image_ids) != len(embeddings):
            raise ValueError("image_ids and embeddings must have the same length")

        if len(image_ids) < self.min_samples:
            # Not enough images to form clusters
            return []

        # Use cosine distance (1 - cosine similarity) for clustering
        distances = pairwise_distances(embeddings, metric="cosine")
        
        # Use tighter threshold for identity clustering to separate different pets
        eps_threshold = self.identity_eps if use_identity_clustering else self.eps
        
        dbscan = DBSCAN(
            eps=eps_threshold,
            min_samples=self.min_samples,
            metric="precomputed",
        )
        labels = dbscan.fit_predict(distances)

        clusters: list[ClusterResult] = []
        for cluster_label in set(labels):
            if cluster_label == -1:  # noise points
                continue

            mask = labels == cluster_label
            cluster_image_ids = [image_ids[i] for i in range(len(image_ids)) if mask[i]]
            cluster_embeddings = embeddings[mask]

            # Compute centroid and rank members by proximity
            centroid = cluster_embeddings.mean(axis=0)
            centroid = centroid / np.linalg.norm(centroid)
            
            similarities = cluster_embeddings @ centroid
            ranked_indices = np.argsort(-similarities)  # descending

            # Limit cluster size
            ranked_indices = ranked_indices[: self.max_cluster_size]
            cluster_image_ids = [cluster_image_ids[i] for i in ranked_indices]

            # Hero is the image closest to centroid
            hero_image_id = cluster_image_ids[0]

            members = [
                ClusterMember(
                    image_id=cluster_image_ids[i],
                    score=float(similarities[ranked_indices[i]]),
                    position=i,
                )
                for i in range(len(cluster_image_ids))
            ]

            quality_score = float(similarities[ranked_indices].mean())

            clusters.append(
                ClusterResult(
                    cluster_id=f"cluster-{cluster_label}",
                    label=self._infer_label(cluster_label, use_identity=use_identity_clustering),
                    hero_image_id=hero_image_id,
                    members=members,
                    quality_score=quality_score,
                )
            )

        return clusters

    def _infer_label(self, cluster_id: int, use_identity: bool = True) -> str:
        """Generate a human-readable label for a cluster."""
        if use_identity:
            # Identity-based labels for different pets
            label_map = {
                0: "Pet A",
                1: "Pet B", 
                2: "Pet C",
                3: "Pet D",
                4: "Pet E",
            }
            return label_map.get(cluster_id, f"Pet {chr(65 + cluster_id)}")
        else:
            # Pose-based labels
            label_map = {
                0: "Portraits",
                1: "Action Shots",
                2: "Close-ups",
                3: "Outdoor Scenes",
                4: "Group Photos",
            }
            return label_map.get(cluster_id % len(label_map), f"Group {cluster_id}")
