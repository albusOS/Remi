"""application/tools — domain tool providers for the agent runtime.

- ``QueryToolProvider``    — single ``query`` tool with in-process resolver dispatch
- ``DocumentToolProvider`` — document list, query, search, and ingestion
- ``register_ingestion_tools`` — pipeline tool setup for the ingestion engine

Note: ``register_ingestion_tools`` is imported directly by its consumer
(``application/ingestion/pipeline.py``), not through this barrel, to
avoid a circular import.
"""

from remi.application.tools.documents import DocumentToolProvider
from remi.application.tools.query import QueryToolProvider

__all__ = [
    "DocumentToolProvider",
    "QueryToolProvider",
    "register_ingestion_tools",
]


def __getattr__(name: str):  # noqa: ANN001
    if name == "register_ingestion_tools":
        from remi.application.tools.ingestion import register_ingestion_tools

        return register_ingestion_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
