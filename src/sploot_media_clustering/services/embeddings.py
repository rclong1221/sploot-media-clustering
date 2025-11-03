"""Image embedding inference using pre-trained vision models."""
from __future__ import annotations

import io
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

try:
    import timm
except ImportError:
    timm = None


class EmbeddingModel:
    """Wraps a vision transformer model for image embedding extraction."""

    def __init__(
        self,
        model_name: str = "vit_small_patch16_224.augreg_in21k",
        device: str | None = None,
    ) -> None:
        if timm is None:
            raise RuntimeError("timm is required for embedding inference")

        # Auto-detect GPU if device not specified
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        elif device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        self.model = timm.create_model(model_name, pretrained=True, num_classes=0)
        self.model = self.model.to(self.device)
        self.model.eval()

        data_config = timm.data.resolve_model_data_config(self.model)
        self.transform = timm.data.create_transform(**data_config, is_training=False)
        
        print(f"EmbeddingModel initialized on device: {self.device}")

    @torch.inference_mode()
    def embed_image(self, image_bytes: bytes) -> np.ndarray:
        """Extract normalized embedding vector from image bytes."""
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        embedding = self.model(tensor).cpu().numpy()[0]
        return embedding / np.linalg.norm(embedding)

    @torch.inference_mode()
    def embed_batch(self, image_bytes_list: list[bytes]) -> np.ndarray:
        """Extract embeddings for a batch of images."""
        images = [Image.open(io.BytesIO(img)).convert("RGB") for img in image_bytes_list]
        tensors = torch.stack([self.transform(img) for img in images]).to(self.device)
        embeddings = self.model(tensors).cpu().numpy()
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / norms


_global_model: EmbeddingModel | None = None


def get_embedding_model(model_name: str | None = None, device: str | None = None) -> EmbeddingModel:
    """Singleton accessor for the embedding model."""
    global _global_model
    if _global_model is None:
        from ..config import get_settings
        settings = get_settings()
        _global_model = EmbeddingModel(
            model_name=model_name or settings.embedding_model_name,
            device=device or settings.embedding_device,
        )
    return _global_model
