"""Manifest registry — capabilities register their app.yaml paths.

Each capability barrel declares a ``MANIFEST_PATH`` constant pointing to
its ``app.yaml``.  At startup the composition root calls
``register_manifest(name, path)`` for each.  The workflow loader and
chat-agent runtime resolve manifests through this registry rather than
scanning a flat directory.

The ``ManifestRegistry`` class is the proper API.  Module-level free
functions (``register_manifest``, ``get_manifest_path``, ``all_manifests``,
``clear``) delegate to a default instance for backward compatibility.
"""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml as _yaml

logger = structlog.get_logger(__name__)


class ManifestRegistry:
    """Named manifest path registry.

    Stores ``{name: Path}`` mappings for agent, pipeline, and workflow
    YAML manifests.  The shell container creates an instance; the
    module-level default instance preserves backward compatibility.
    """

    def __init__(self) -> None:
        self._manifests: dict[str, Path] = {}
        self._kind_cache: dict[str, str] = {}

    def register(self, name: str, path: Path) -> None:
        """Register a named manifest (agent or workflow YAML)."""
        if not path.exists():
            logger.warning("manifest_not_found", name=name, path=str(path))
        self._manifests[name] = path

    def get_path(self, name: str) -> Path:
        """Return the path for a registered manifest, or raise."""
        if name not in self._manifests:
            raise ValueError(f"Unknown manifest: {name!r}. Registered: {sorted(self._manifests)}")
        return self._manifests[name]

    def all_manifests(self) -> dict[str, Path]:
        """Return a copy of every registered manifest."""
        return dict(self._manifests)

    def has(self, name: str) -> bool:
        """Return ``True`` if *name* is registered."""
        return name in self._manifests

    def get_kind(self, name: str) -> str:
        """Return the ``kind`` (Agent, Pipeline, Workflow) for a manifest.

        Reads the YAML file and caches the result so repeated lookups
        don't re-parse.
        """
        if name in self._kind_cache:
            return self._kind_cache[name]
        path = self.get_path(name)
        kind = "Agent"
        if path.exists():
            try:
                with open(path) as f:
                    data = _yaml.safe_load(f)
                kind = data.get("kind", "Agent") if isinstance(data, dict) else "Agent"
            except Exception:
                logger.warning("manifest_kind_read_failed", name=name, exc_info=True)
        self._kind_cache[name] = kind
        return kind

    def clear(self) -> None:
        """Reset the registry (for tests)."""
        self._manifests.clear()
        self._kind_cache.clear()

    def __len__(self) -> int:
        return len(self._manifests)

    def __repr__(self) -> str:
        return f"ManifestRegistry({sorted(self._manifests)})"


# -- Module-level default instance + backward-compat wrappers ---------------

_default = ManifestRegistry()


def default_registry() -> ManifestRegistry:
    """Return the module-level default registry instance.

    Products that populate manifests before kernel boot pass this
    into ``Kernel.boot(registry=default_registry())`` so the kernel
    uses the same registry for workforce construction and agent loading.
    """
    return _default


def register_manifest(name: str, path: Path) -> None:
    """Register a named manifest on the default registry."""
    _default.register(name, path)


def get_manifest_path(name: str) -> Path:
    """Return the path for a registered manifest from the default registry."""
    return _default.get_path(name)


def all_manifests() -> dict[str, Path]:
    """Return a copy of every registered manifest from the default registry."""
    return _default.all_manifests()


def get_manifest_kind(name: str) -> str:
    """Return the ``kind`` for a manifest from the default registry."""
    return _default.get_kind(name)


def clear() -> None:
    """Reset the default registry (for tests)."""
    _default.clear()


def discover_manifests(
    root: str | Path,
    *,
    pattern: str = "**/app.yaml",
    registry: ManifestRegistry | None = None,
) -> int:
    """Scan *root* for manifest files and register each one.

    Returns the number of manifests registered.  Uses the ``metadata.name``
    field from each YAML as the registry key.  Files that lack
    ``metadata.name`` or a recognised ``kind`` are skipped with a warning.
    """
    root = Path(root)
    target = registry or _default
    count = 0
    for path in sorted(root.glob(pattern)):
        try:
            with open(path) as f:
                data = _yaml.safe_load(f)
            if not isinstance(data, dict):
                continue
            kind = data.get("kind", "")
            if kind not in ("Agent", "Pipeline", "Workflow"):
                continue
            name = (data.get("metadata") or {}).get("name")
            if not name:
                logger.warning("manifest_missing_name", path=str(path))
                continue
            target.register(name, path)
            count += 1
        except Exception:
            logger.warning("manifest_discover_error", path=str(path), exc_info=True)
    return count
