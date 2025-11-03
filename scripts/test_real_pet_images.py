#!/usr/bin/env python3
"""
Test clustering with real pet images from local filesystem.
This script creates a temporary storage service that serves real pet images.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
import uvicorn


# Configuration
PET_IMAGES_DIR = Path("/Users/dollerinho/sploot/Pet Images/Shamu")
REDIS_URL = "redis://localhost:6379/0"
STORAGE_PORT = 8001  # Use different port to avoid conflicts
AUTH_TOKEN = "test-token-123"


def get_real_pet_images() -> List[Path]:
    """Get list of real pet images from filesystem."""
    images = []
    for ext in ["*.jpg", "*.jpeg", "*.JPG", "*.JPEG", "*.png", "*.PNG"]:
        images.extend(PET_IMAGES_DIR.glob(ext))
    return sorted(images)[:15]  # Limit to 15 images for testing


# Create FastAPI app for serving real images
app = FastAPI(title="Real Pet Images Storage Service")


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/images/{image_id}")
async def get_image(image_id: str, authorization: str = Header(None)):
    """Serve real pet images."""
    if not authorization or authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Map image_id to actual file
    images = get_real_pet_images()
    try:
        idx = int(image_id.split("-")[-1]) - 1
        if 0 <= idx < len(images):
            image_path = images[idx]
            if image_path.exists():
                return FileResponse(image_path, media_type="image/jpeg")
    except (ValueError, IndexError):
        pass
    
    raise HTTPException(status_code=404, detail="Image not found")


async def enqueue_clustering_job(pet_id: str, image_ids: List[str]):
    """Enqueue a clustering job in Redis Streams."""
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    try:
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


async def wait_for_results(pet_id: str, timeout: int = 60) -> dict:
    """Poll Redis for clustering results."""
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    try:
        key = f"pet:{pet_id}:clustering"
        
        for _ in range(timeout):
            results = await redis_client.hget(key, "results")
            if results:
                return json.loads(results)
            await asyncio.sleep(1)
        
        raise TimeoutError(f"No results after {timeout} seconds")
    finally:
        await redis_client.aclose()


async def run_test():
    """Main test orchestration."""
    # Get real images
    images = get_real_pet_images()
    if not images:
        print(f"❌ No images found in {PET_IMAGES_DIR}")
        return
    
    print(f"\n🐾 Testing with {len(images)} real pet images from Shamu folder")
    print(f"Images: {', '.join([img.name for img in images[:5]])}{'...' if len(images) > 5 else ''}\n")
    
    # Create image IDs
    image_ids = [f"real-pet-{i+1}" for i in range(len(images))]
    pet_id = "shamu-test"
    
    # Enqueue job
    print(f"Enqueuing clustering job for pet '{pet_id}'...")
    await enqueue_clustering_job(pet_id, image_ids)
    
    print("Waiting for worker to process (this may take 30-60s for real images)...\n")
    
    # Wait for results
    try:
        results = await wait_for_results(pet_id, timeout=120)
        
        print("✓ Clustering complete!\n")
        print("=" * 60)
        print(f"Pet ID: {pet_id}")
        print(f"Total Images: {len(images)}")
        print(f"Clusters Found: {results.get('num_clusters', 0)}")
        print(f"Average Quality: {results.get('avg_quality', 0):.3f}")
        print(f"Processed At: {results.get('processed_at', 'unknown')}")
        print("=" * 60)
        
        # Display clusters
        clusters = results.get("clusters", {})
        for cluster_id, cluster_data in clusters.items():
            print(f"\n📸 Cluster {cluster_id}: {cluster_data.get('label', 'Unknown')}")
            print(f"   Hero: {cluster_data.get('hero_image')}")
            print(f"   Size: {cluster_data.get('size')} images")
            print(f"   Quality: {cluster_data.get('quality', 0):.3f}")
            
            members = cluster_data.get("members", [])[:5]  # Show first 5
            print(f"   Top Members:")
            for member in members:
                img_idx = int(member["image_id"].split("-")[-1]) - 1
                img_name = images[img_idx].name if img_idx < len(images) else "unknown"
                print(f"      - {img_name} (score: {member['score']:.3f})")
        
        print("\n✅ Test completed successfully!")
        
    except TimeoutError as e:
        print(f"❌ {e}")
        print("\nCheck worker logs:")
        print("  docker logs sploot_media_clustering-media-clustering-worker-1 --tail 50")


def start_storage_server():
    """Start the storage service in the background."""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=STORAGE_PORT,
        log_level="error",  # Quiet
        access_log=False,
    )
    server = uvicorn.Server(config)
    
    print(f"🚀 Starting storage service on http://localhost:{STORAGE_PORT}")
    print(f"   Serving {len(get_real_pet_images())} images from: {PET_IMAGES_DIR}\n")
    
    # Run in background
    import threading
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    
    # Give server time to start
    import time
    time.sleep(2)


if __name__ == "__main__":
    # Start storage server
    start_storage_server()
    
    # Run test
    asyncio.run(run_test())
