#!/usr/bin/env python3
"""
Test clustering with real Shamu pet images.
Sends 15 real pet images through the clustering pipeline.
"""

import asyncio
import json
import sys

import redis.asyncio as redis


REDIS_URL = "redis://localhost:6379/0"
AUTH_TOKEN = "test-token-123"


async def enqueue_clustering_job(pet_id: str, num_images: int):
    """Enqueue a clustering job for real pet images."""
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    try:
        # Create image IDs for the 15 real Shamu images
        image_ids = [f"pet-1-img-{i+1}" for i in range(num_images)]
        
        job_data = {
            "pet_id": pet_id,
            "image_ids": json.dumps(image_ids),
            "storage_token": AUTH_TOKEN,
        }
        
        message_id = await redis_client.xadd("media:clustering:jobs", job_data)
        print(f"✓ Job enqueued with ID: {message_id}")
        return message_id
    finally:
        await redis_client.aclose()


async def wait_for_results(pet_id: str, timeout: int = 120) -> dict:
    """Poll Redis for clustering results."""
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    try:
        key = f"pet:{pet_id}:clustering"
        
        print(f"Waiting for clustering results (timeout: {timeout}s)...")
        for i in range(timeout):
            if i > 0 and i % 10 == 0:
                print(f"  ... still waiting ({i}s elapsed)")
            
            results = await redis_client.hget(key, "results")
            if results:
                return json.loads(results)
            await asyncio.sleep(1)
        
        raise TimeoutError(f"No results after {timeout} seconds")
    finally:
        await redis_client.aclose()


async def main():
    pet_id = "shamu-real"
    num_images = 15
    
    print("\n🐾 Testing ML Clustering with REAL Shamu Pet Images")
    print("=" * 70)
    print(f"Pet ID: {pet_id}")
    print(f"Images: {num_images} real photos from /Pet Images/Shamu")
    print("=" * 70)
    print()
    
    # Enqueue job
    await enqueue_clustering_job(pet_id, num_images)
    
    # Wait for results
    try:
        results = await wait_for_results(pet_id, timeout=120)
        
        print("\n✅ Clustering Complete!")
        print("=" * 70)
        print(f"Total Images: {results.get('num_images', 0)}")
        print(f"Clusters Found: {results.get('num_clusters', 0)}")
        print(f"Average Quality: {results.get('avg_quality', 0):.3f}")
        print(f"Processed At: {results.get('processed_at', 'unknown')}")
        print("=" * 70)
        
        # Display clusters
        clusters = results.get("clusters", {})
        for cluster_id, cluster_data in sorted(clusters.items()):
            print(f"\n📸 Cluster {cluster_id}: {cluster_data.get('label', 'Unknown')}")
            print(f"   Hero Image: {cluster_data.get('hero_image')}")
            print(f"   Size: {cluster_data.get('size')} images")
            print(f"   Quality Score: {cluster_data.get('quality', 0):.3f}")
            
            members = cluster_data.get("members", [])
            print(f"   Members:")
            for member in members:
                print(f"      - {member['image_id']} (score: {member['score']:.3f})")
        
        print("\n🎉 Test completed successfully!")
        return 0
        
    except TimeoutError as e:
        print(f"\n❌ {e}")
        print("\nCheck worker logs:")
        print("  docker logs sploot_media_clustering-media-clustering-worker-1 --tail 50")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
