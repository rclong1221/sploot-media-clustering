"""End-to-end test for the clustering pipeline with real images."""
import asyncio
import json

from sploot_media_clustering.config import get_settings
from sploot_media_clustering.infrastructure.redis import get_redis_client
from sploot_media_clustering.services.clustering import cluster_service


async def test_clustering_pipeline():
    """Test the full pipeline: enqueue job → worker processes → fetch results."""
    settings = get_settings()
    redis = get_redis_client()
    
    # Enqueue a test job with all 13 real Shamu images
    pet_id = "shamu"
    job_payload = {
        "image_ids": [
            "pet-1-img-1",
            "pet-1-img-2",
            "pet-1-img-3",
            "pet-1-img-4",
            "pet-1-img-5",
            "pet-1-img-6",
            "pet-1-img-7",
            "pet-1-img-8",
            "pet-1-img-9",
            "pet-1-img-10",
            "pet-1-img-11",
            "pet-1-img-12",
            "pet-1-img-13",
        ],
        "reason": "real Shamu pet photos test",
    }
    
    print(f"Enqueuing job for pet {pet_id}...")
    await cluster_service.enqueue_job(pet_id, job_payload)
    print("Job enqueued. Waiting for worker to process...")
    
    # Poll for results (worker should process within seconds)
    max_attempts = 30
    for attempt in range(max_attempts):
        await asyncio.sleep(1)
        state = await cluster_service.get_cluster_state(pet_id)
        if state:
            print(f"\n✓ Clustering complete after {attempt + 1} seconds!")
            print(f"\nResults:")
            print(f"  Pet ID: {state.pet_id}")
            print(f"  Clusters: {len(state.clusters)}")
            print(f"  Metrics: {json.dumps(state.metrics, indent=2)}")
            
            for i, cluster in enumerate(state.clusters):
                print(f"\n  Cluster {i + 1}: {cluster['label']}")
                print(f"    Hero: {cluster['hero_image_id']}")
                print(f"    Members: {len(cluster['members'])}")
                for member in cluster["members"][:3]:  # Show first 3
                    print(f"      - {member['image_id']} (score: {member['score']:.3f})")
            
            return
    
    print(f"\n✗ Timeout: No results after {max_attempts} seconds")
    print("Ensure the worker is running: docker compose -f docker-compose.local.yml up media-clustering-worker")


if __name__ == "__main__":
    asyncio.run(test_clustering_pipeline())
