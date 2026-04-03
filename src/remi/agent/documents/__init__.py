"""Document management — types, stores, parsers.

Public API::

    from remi.agent.documents import Document, DocumentStore, parse_document
"""

from remi.agent.documents.parsers import parse_document
from remi.agent.documents.types import Document, DocumentStore

__all__ = [
    "Document",
    "DocumentStore",
    "parse_document",
]
