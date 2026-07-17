import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.embedding_api_key and self.settings.embedding_model)

    async def embed(self, text: str) -> list[float]:
        if not self.configured:
            raise RuntimeError("embedding_provider_not_configured")
        payload = {"model": self.settings.embedding_model, "input": text}
        headers = {"Authorization": f"Bearer {self.settings.embedding_api_key}"}
        url = f"{self.settings.embedding_base_url.rstrip('/')}/embeddings"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        embedding = response.json()["data"][0]["embedding"]
        if not isinstance(embedding, list) or len(embedding) != self.settings.embedding_dimensions:
            logger.warning("embedding_invalid_dimension expected=%d", self.settings.embedding_dimensions)
            raise ValueError("embedding_dimension_mismatch")
        return [float(value) for value in embedding]
