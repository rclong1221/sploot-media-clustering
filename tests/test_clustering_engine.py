"""Tests for the clustering engine."""
import numpy as np
import pytest

from sploot_media_clustering.services.clustering_engine import ClusteringEngine


def test_cluster_images_basic():
    """Test basic clustering with synthetic embeddings."""
    engine = ClusteringEngine(eps=0.3, min_samples=2, max_cluster_size=10)
    
    # Create two clear clusters in embedding space
    # Cluster 1: embeddings near [1, 0, 0, ...]
    cluster1_embeds = np.array([
        [1.0, 0.1, 0.0],
        [0.9, 0.2, 0.1],
        [1.1, 0.0, 0.1],
    ])
    
    # Cluster 2: embeddings near [0, 1, 0, ...]
    cluster2_embeds = np.array([
        [0.1, 1.0, 0.0],
        [0.2, 0.9, 0.1],
    ])
    
    embeddings = np.vstack([cluster1_embeds, cluster2_embeds])
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    image_ids = [f"img-{i}" for i in range(5)]
    
    results = engine.cluster_images(image_ids, embeddings)
    
    assert len(results) == 2
    assert all(r.quality_score > 0 for r in results)
    assert all(len(r.members) > 0 for r in results)
    
    # Check hero selection
    for result in results:
        assert result.hero_image_id == result.members[0].image_id


def test_cluster_images_insufficient_samples():
    """Test clustering with too few images."""
    engine = ClusteringEngine(eps=0.3, min_samples=3, max_cluster_size=10)
    
    embeddings = np.random.randn(2, 128)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    image_ids = ["img-0", "img-1"]
    
    results = engine.cluster_images(image_ids, embeddings)
    
    # Not enough samples to form any clusters
    assert len(results) == 0


def test_cluster_images_size_limit():
    """Test that clusters are capped at max_cluster_size."""
    engine = ClusteringEngine(eps=0.5, min_samples=2, max_cluster_size=3)
    
    # Create one tight cluster with many members
    embeddings = np.random.randn(10, 64)
    centroid = np.array([1.0] + [0.0] * 63)
    embeddings = 0.9 * centroid + 0.1 * embeddings  # all close to centroid
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    image_ids = [f"img-{i}" for i in range(10)]
    
    results = engine.cluster_images(image_ids, embeddings)
    
    assert len(results) >= 1
    for result in results:
        assert len(result.members) <= 3


def test_cluster_images_mismatched_lengths():
    """Test error handling for mismatched inputs."""
    engine = ClusteringEngine()
    
    embeddings = np.random.randn(5, 128)
    image_ids = ["img-0", "img-1", "img-2"]
    
    with pytest.raises(ValueError, match="must have the same length"):
        engine.cluster_images(image_ids, embeddings)
