"""Mock storage service for testing image clustering locally."""
import asyncio
import io
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from PIL import Image
import numpy as np

app = FastAPI(title="Mock Storage Service")

# Toggle between synthetic and real pet images
USE_REAL_IMAGES = os.getenv("USE_REAL_IMAGES", "false").lower() == "true"
# In Docker, this will be /pet-images/Shamu (mounted volume)
# On host, this will be the actual path
REAL_PET_IMAGES_DIR = Path(os.getenv("REAL_PET_IMAGES_PATH", "/pet-images/Shamu"))

# Generate synthetic pet images in memory
MOCK_IMAGES: dict[str, bytes] = {}


def generate_mock_image(image_id: str, color: tuple[int, int, int]) -> bytes:
    """Generate a synthetic colored image."""
    img = Image.new("RGB", (224, 224), color)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def load_real_pet_images() -> dict[str, bytes]:
    """Load real pet images from filesystem."""
    images = {}
    if not REAL_PET_IMAGES_DIR.exists():
        print(f"Warning: Real images directory not found: {REAL_PET_IMAGES_DIR}")
        return images
    
    # Get first 15 image files
    image_files = []
    for ext in ["*.jpg", "*.jpeg", "*.JPG", "*.JPEG", "*.png", "*.PNG"]:
        image_files.extend(REAL_PET_IMAGES_DIR.glob(ext))
    
    image_files = sorted(image_files)[:15]
    
    for idx, image_path in enumerate(image_files, start=1):
        try:
            with open(image_path, "rb") as f:
                images[f"pet-1-img-{idx}"] = f.read()
            print(f"Loaded real image: pet-1-img-{idx} ({image_path.name})")
        except Exception as e:
            print(f"Failed to load {image_path}: {e}")
    
    return images


# Load images based on configuration
if USE_REAL_IMAGES:
    print(f"Loading REAL pet images from: {REAL_PET_IMAGES_DIR}")
    MOCK_IMAGES = load_real_pet_images()
    print(f"Loaded {len(MOCK_IMAGES)} real pet images")
else:
    print("Using SYNTHETIC pet images")
    # Pre-generate mock images with different colors for clustering
    MOCK_IMAGES["pet-1-img-1"] = generate_mock_image("pet-1-img-1", (255, 100, 100))  # Red cluster
    MOCK_IMAGES["pet-1-img-2"] = generate_mock_image("pet-1-img-2", (250, 110, 105))
    MOCK_IMAGES["pet-1-img-3"] = generate_mock_image("pet-1-img-3", (255, 95, 110))
    MOCK_IMAGES["pet-1-img-4"] = generate_mock_image("pet-1-img-4", (100, 100, 255))  # Blue cluster
    MOCK_IMAGES["pet-1-img-5"] = generate_mock_image("pet-1-img-5", (105, 110, 250))
    MOCK_IMAGES["pet-1-img-6"] = generate_mock_image("pet-1-img-6", (95, 105, 255))
    MOCK_IMAGES["pet-1-img-7"] = generate_mock_image("pet-1-img-7", (100, 255, 100))  # Green cluster
    MOCK_IMAGES["pet-1-img-8"] = generate_mock_image("pet-1-img-8", (110, 250, 105))


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/images/{image_id}")
async def get_image(image_id: str, authorization: str = Header(None)):
    """Fetch a mock image by ID."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    if image_id not in MOCK_IMAGES:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    
    from fastapi.responses import Response
    return Response(content=MOCK_IMAGES[image_id], media_type="image/jpeg")


if __name__ == "__main__":
    import uvicorn
    print("Starting mock storage service on http://localhost:8000")
    print(f"Available images: {list(MOCK_IMAGES.keys())}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
