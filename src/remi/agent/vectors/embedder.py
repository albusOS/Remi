"""Embedder port default + factory.

``NoopEmbedder`` is the zero-dep deterministic fallback for tests and offline
dev.  External provider adapters live in ``remi.agent.vectors.adapters``.

``build_embedder`` selects the right implementation from settings.
"""

from __future__ import annotations

import hashlib
import importlib
import math

import structlog

from remi.agent.llm.types import SecretsSettings
from remi.agent.vectors.types import EmbeddingsSettings
from remi.agent.vectors.types import Embedder

_log = structlog.get_logger(__name__)

_ADAPTERS: dict[str, tuple[str, str]] = {
    "openai": ("remi.agent.vectors.adapters.openai_embedder", "OpenAIEmbedder"),
}


class NoopEmbedder(Embedder):
    """Deterministic pseudo-embedder for tests and offline development.

    Produces reproducible vectors derived from text hashing — not semantically
    meaningful, but structurally valid and deterministic. Logs a warning at
    construction time so it is obvious when real embeddings are not being used.
    """

    def __init__(self, dimension: int = 128, *, silent: bool = False) -> None:
        self._dimension = dimension
        if not silent:
            _log.warning(
                "noop_embedder_active",
                message=(
                    "No embedding provider is configured — using NoopEmbedder. "
                    "Semantic search will not return meaningful results. "
                    "Set REMI_EMBEDDINGS_PROVIDER and the corresponding API key "
                    "to enable real embeddings."
                ),
            )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(t) for t in texts]

    async def embed_one(self, text: str) -> list[float]:
        return self._hash_embed(text)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        raw: list[float] = []
        while len(raw) < self._dimension:
            raw.extend(b / 255.0 * 2 - 1 for b in h)
            h = hashlib.sha256(h).digest()
        raw = raw[: self._dimension]
        norm = math.sqrt(sum(x * x for x in raw))
        if norm > 0:
            raw = [x / norm for x in raw]
        return raw


def build_embedder(cfg: EmbeddingsSettings, secrets: SecretsSettings) -> Embedder:
    """Select and construct an embedder from settings."""
    provider = cfg.provider.lower()

    adapter = _ADAPTERS.get(provider)
    if adapter is not None and secrets.openai_api_key:
        module_path, class_name = adapter
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls(
            model=cfg.model,
            api_key=secrets.openai_api_key,
            dimensions=cfg.dimensions,
        )

    return NoopEmbedder()
