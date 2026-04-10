"""OpenAI embedding adapter.

Requires the ``openai`` package and a valid API key.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from remi.agent.vectors.types import Embedder

_log = structlog.get_logger(__name__)


class OpenAIEmbedder(Embedder):
    """Embeds text using OpenAI's embedding API.

    Batches requests for efficiency (OpenAI supports up to 2048 inputs per call).
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        dimensions: int = 1536,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._dimensions = dimensions
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "OpenAIEmbedder requires the 'openai' package. "
                    "Install with: pip install 'remi[openai]'"
                ) from exc
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        cleaned = [t[:8191] for t in texts]
        _log.debug("embedding_batch", count=len(cleaned), model=self._model)
        response = await client.embeddings.create(
            input=cleaned,
            model=self._model,
            dimensions=self._dimensions,
        )
        return [item.embedding for item in response.data]

    async def embed_one(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]

    @property
    def dimension(self) -> int:
        return self._dimensions
