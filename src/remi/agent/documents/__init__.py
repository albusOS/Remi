"""Document content management — types, stores, parsers.

Public API::

    from remi.agent.documents import (
        DocumentContent, ContentStore, parse_document, build_content_store,
    )
"""

from remi.agent.documents.adapters.parsers import parse_document
from remi.agent.documents.factory import build_content_store
from remi.agent.documents.types import (
    ContentStore,
    DocumentContent,
    DocumentKind,
    TextChunk,
)

__all__ = [
    "ContentStore",
    "DocumentContent",
    "DocumentKind",
    "TextChunk",
    "build_content_store",
    "parse_document",
]
