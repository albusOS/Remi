"""Manifest registry — capabilities register their app.yaml paths.

Each capability barrel declares a ``MANIFEST_PATH`` constant pointing to
its ``app.yaml``.  At startup the composition root calls
``register_manifest(name, path)`` for each.  The workflow loader and
chat-agent runtime resolve manifests through this registry rather than
scanning a flat directory.
"""

from __future__ import annotations

from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_manifests: dict[str, Path] = {}


def register_manifest(name: str, path: Path) -> None:
    """Register a named manifest (agent or workflow YAML)."""
    if not path.exists():
        logger.warning("manifest_not_found", name=name, path=str(path))
    _manifests[name] = path


def get_manifest_path(name: str) -> Path:
    """Return the path for a registered manifest, or raise."""
    if name not in _manifests:
        raise ValueError(
            f"Unknown manifest: {name!r}. Registered: {sorted(_manifests)}"
        )
    return _manifests[name]


def all_manifests() -> dict[str, Path]:
    """Return a copy of every registered manifest."""
    return dict(_manifests)


def clear() -> None:
    """Reset the registry (for tests)."""
    _manifests.clear()
