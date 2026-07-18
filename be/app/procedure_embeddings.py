"""Local embeddings used exclusively by the DVC procedure snapshot."""

import asyncio
from functools import lru_cache

from app.config import Settings


class ProcedureEmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    @lru_cache
    def _model(model_name: str, device: str):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name, device=device, local_files_only=True)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._model(self.settings.procedure_embedding_model, self.settings.procedure_embedding_device)
        vectors = await asyncio.to_thread(model.encode, texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        result = [[float(value) for value in vector] for vector in vectors]
        if any(len(vector) != self.settings.procedure_embedding_dimensions for vector in result):
            raise ValueError("procedure_embedding_dimension_mismatch")
        return result

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_many([text]))[0]
