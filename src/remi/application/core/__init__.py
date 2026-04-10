"""Domain — pure business logic with no infrastructure dependencies.

Public API::

    from remi.application.core import PropertyStore
    from remi.application.core import ChangeSet, EventStore, ...
"""

from remi.application.core.events import (
    ChangeEvent,
    ChangeSet,
    ChangeSource,
    ChangeType,
    EventStore,
    FieldChange,
)
from remi.application.core.protocols import (
    DocumentIngester,
    EmbedRequest,
    PropertyStore,
    TextIndexer,
    TextSearchHit,
    UploadResult,
    VectorSearch,
)

__all__ = [
    "ChangeEvent",
    "ChangeSet",
    "ChangeSource",
    "ChangeType",
    "DocumentIngester",
    "EmbedRequest",
    "EventStore",
    "FieldChange",
    "PropertyStore",
    "TextIndexer",
    "TextSearchHit",
    "UploadResult",
    "VectorSearch",
]
