"""application/tools — domain tools and service functions.

- ``register_ingestion_tools`` — pipeline tool setup for the ingestion engine.

Service functions (``assertions.py``) are consumed by API routes directly.
"""

from remi.application.tools.ingestion import register_ingestion_tools

__all__ = [
    "register_ingestion_tools",
]
