"""Graph retrieval — entity resolution and schema introspection.

- GraphRetriever: fuses vector similarity with graph traversal
- ResolvedEntity / RetrievalResult: retrieval output DTOs
- pydantic_to_type_def / schemas_for_prompt: schema introspection utilities
"""

from remi.agent.graph.retrieval.introspect import (
    pydantic_to_type_def,
    pydantic_to_type_defs,
    schemas_for_prompt,
)
from remi.agent.graph.retrieval.retriever import (
    GraphRetriever,
    ResolvedEntity,
    RetrievalResult,
)

__all__ = [
    "GraphRetriever",
    "ResolvedEntity",
    "RetrievalResult",
    "pydantic_to_type_def",
    "pydantic_to_type_defs",
    "schemas_for_prompt",
]
