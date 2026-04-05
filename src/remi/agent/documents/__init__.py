"""Document management — types, stores, parsers.

Public API::

    from remi.agent.documents import Document, DocumentStore, parse_document
"""

from remi.agent.documents.parsers import parse_document
from remi.agent.documents.types import (
    Document,
    DocumentKind,
    DocumentStore,
    TextChunk,
)

__all__ = [
    "Document",
    "DocumentKind",
    "DocumentStore",
    "TextChunk",
    "parse_document",
]
