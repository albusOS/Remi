"""Vector subsystem — embeddings, storage, search, and token estimation.

Public API::

    from remi.agent.vectors import VectorStore, Embedder, build_vector_store, build_embedder
"""

from remi.agent.vectors.embedder import build_embedder
from remi.agent.vectors.factory import build_vector_store
from remi.agent.vectors.types import (
    Embedder,
    EmbeddingRecord,
    EmbeddingRequest,
    SearchResult,
    VectorStore,
)

__all__ = [
    "Embedder",
    "EmbeddingRecord",
    "EmbeddingRequest",
    "SearchResult",
    "VectorStore",
    "build_embedder",
    "build_vector_store",
]
