"""Client for fetching image data from storage service."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class StorageClient:
    """Interface to fetch image bytes from the image storage service."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._internal_base_url = self._ensure_internal_base(self.base_url)

    @staticmethod
    def _ensure_internal_base(base_url: str) -> str:
        """Ensure requests target the internal API namespace exactly once."""
        if base_url.endswith("/internal"):
            return base_url
        if base_url.endswith("/internal/"):
            return base_url.rstrip("/")
        return f"{base_url}/internal"

    def _internal_url(self, path: str) -> str:
        return f"{self._internal_base_url}/{path.lstrip('/')}"

    async def fetch_image(self, image_id: str) -> bytes:
        """Fetch a single image by ID."""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            url = self._internal_url(f"images/{image_id}")
            headers = {"Authorization": f"Bearer {self.api_token}"}
            
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.read()

    async def fetch_images_batch(self, image_ids: list[str]) -> dict[str, bytes]:
        """
        Fetch multiple images concurrently.
        
        Returns:
            Dictionary mapping image_id to image bytes. Failed fetches are omitted.
        """
        async def _fetch_one(image_id: str) -> tuple[str, bytes | None]:
            try:
                data = await self.fetch_image(image_id)
                return image_id, data
            except Exception as exc:
                import logging
                logging.error(f"Failed to fetch {image_id}: {type(exc).__name__}: {exc}")
                return image_id, None

        results = await asyncio.gather(*[_fetch_one(img_id) for img_id in image_ids])
        return {img_id: data for img_id, data in results if data is not None}

    async def fetch_insight(self, image_id: str) -> dict[str, Any] | None:
        """
        Fetch photo insights for an image, including embedding.
        
        Args:
            image_id: ID of the source image
            
        Returns:
            Dictionary containing insight data including embedding, or None if not found
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            url = self._internal_url(f"insights/{image_id}")
            headers = {"Authorization": f"Bearer {self.api_token}"}
            
            try:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as exc:
                import logging
                logging.warning(f"Failed to fetch insight for {image_id}: {type(exc).__name__}: {exc}")
                return None

    async def fetch_insights_batch(self, image_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Fetch insights for multiple images concurrently.
        
        Returns:
            Dictionary mapping image_id to insight data. Failed fetches are omitted.
        """
        async def _fetch_one(image_id: str) -> tuple[str, dict[str, Any] | None]:
            insight = await self.fetch_insight(image_id)
            return image_id, insight

        results = await asyncio.gather(*[_fetch_one(img_id) for img_id in image_ids])
        return {img_id: data for img_id, data in results if data is not None}

    async def fetch_pet_images_with_embeddings(self, pet_id: int) -> list[str]:
        """
        Fetch list of all image IDs that have embeddings for a pet.
        
        Args:
            pet_id: ID of the pet
            
        Returns:
            List of image IDs (as strings) that have embeddings
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            url = self._internal_url(f"pets/{pet_id}/images-with-embeddings")
            headers = {"Authorization": f"Bearer {self.api_token}"}
            
            try:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return [str(img_id) for img_id in data.get("image_ids", [])]
            except Exception as exc:
                import logging
                logging.error(f"Failed to fetch pet images with embeddings: {type(exc).__name__}: {exc}")
                return []

    async def store_insight(
        self,
        source_image_id: int,
        embedding: list[float] | None = None,
        species: str | None = None,
        quality_score: float | None = None,
        pose_category: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Store photo insights for an image.
        
        Args:
            source_image_id: ID of the source image
            embedding: Embedding vector (512-dim list)
            species: Detected species ('dog', 'cat', etc.)
            quality_score: Overall quality score
            pose_category: Pose category ('sitting', 'standing', etc.)
            **kwargs: Additional insight fields
            
        Returns:
            Response data from the insights API
        """
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            url = self._internal_url("insights")
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "source_image_id": source_image_id,
                "embedding": embedding,
                "species": species,
                "quality_score": quality_score,
                "pose_category": pose_category,
                **kwargs,
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                return await response.json()

    async def store_insights_batch(
        self,
        insights: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Store multiple photo insights concurrently.
        
        Args:
            insights: List of insight dictionaries, each containing at least 'source_image_id'
            
        Returns:
            List of response data from the insights API
        """
        async def _store_one(insight: dict[str, Any]) -> dict[str, Any] | None:
            try:
                return await self.store_insight(**insight)
            except Exception as exc:
                import logging
                logging.error(
                    f"Failed to store insight for image {insight.get('source_image_id')}: "
                    f"{type(exc).__name__}: {exc}"
                )
                return None

        results = await asyncio.gather(*[_store_one(insight) for insight in insights])
        return [r for r in results if r is not None]


_global_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    """Singleton accessor for storage client."""
    global _global_client
    if _global_client is None:
        from ..config import get_settings
        settings = get_settings()
        _global_client = StorageClient(
            base_url=settings.storage_service_url,
            api_token=settings.internal_service_token,
        )
    return _global_client
