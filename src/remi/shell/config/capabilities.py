"""Capability registry — auto-discovered manifests + shell wiring.

Agent manifests (``app.yaml``) are **auto-discovered** by scanning
``application/`` for YAML files with ``kind: Agent``, ``Pipeline``, or
``Workflow``.  Each manifest's ``metadata.name`` becomes its registry
key — no Python table entry is needed just to register a manifest.

Shell concerns — API routers and CLI groups — are declared in a small
Python table (``_shell_wiring``).  These are matched to discovered
manifests by the manifest's ``metadata.name`` field.  If a wiring
entry's ``manifest_name`` matches a discovered manifest, the two are
merged so a single ``CapabilityDescriptor`` carries both the manifest
path and the router/CLI refs.

At startup the DI container (and CLI entrypoint) call
``ensure_capabilities_registered()`` which:

1. Discovers all ``app.yaml`` manifests under ``application/``.
2. Registers each manifest in the workflow registry.
3. Merges any shell wiring that references the same manifest name.
4. Registers shell-only capabilities (no manifest) like ``agents`` and
   ``events``.

This module lives in ``shell/`` because the capability concept (routers,
CLI groups, manifest wiring) is a **composition-root concern**.  Inner
layers (``agent/``, ``application/``) never import from here.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

from remi.agent.workflow.registry import register_manifest

logger = structlog.get_logger(__name__)

_capabilities: dict[str, CapabilityDescriptor] = {}

_KNOWN_KINDS = {"Agent", "Pipeline", "Workflow"}


# ---------------------------------------------------------------------------
# Descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Self-describing application capability — pure data, no heavy imports.

    ``router_refs`` and ``cli_ref`` are dotted-path strings
    (``"module.path:attribute"``) that resolve to live objects only when
    the shell calls ``resolve_routers`` or ``resolve_cli_group``.

    ``manifest_name`` overrides the key used when registering the
    manifest in the workflow registry.  Needed when the capability
    name (``portfolio``) differs from the YAML ``metadata.name``
    (``manager_review``).  Auto-set during discovery/merge.
    """

    name: str
    manifest: Path | None = None
    manifest_name: str | None = None
    router_refs: tuple[str, ...] = field(default_factory=tuple)
    cli_ref: str | None = None
    api_prefix: str = "/api/v1"


# ---------------------------------------------------------------------------
# Lazy resolution helpers
# ---------------------------------------------------------------------------


def _import_attr(dotted: str) -> Any:
    """Import ``module.path:attribute``."""
    module_path, attr_name = dotted.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, attr_name)


def resolve_routers(cap: CapabilityDescriptor) -> list[Any]:
    """Lazily import and return the APIRouter objects for a capability."""
    return [_import_attr(ref) for ref in cap.router_refs]


def resolve_cli_group(cap: CapabilityDescriptor) -> Any | None:
    """Lazily import and return the Typer CLI group, or ``None``."""
    if cap.cli_ref is None:
        return None
    return _import_attr(cap.cli_ref)


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------


def register(cap: CapabilityDescriptor) -> None:
    """Register a capability and forward its manifest to the workflow registry."""
    _capabilities[cap.name] = cap
    if cap.manifest is not None:
        mname = cap.manifest_name or cap.name
        register_manifest(mname, cap.manifest)
    logger.debug("capability_registered", name=cap.name)


def get_capability(name: str) -> CapabilityDescriptor:
    """Return a registered capability by name, or raise."""
    if name not in _capabilities:
        raise ValueError(f"Unknown capability: {name!r}. Registered: {sorted(_capabilities)}")
    return _capabilities[name]


def all_capabilities() -> dict[str, CapabilityDescriptor]:
    """Return a copy of every registered capability."""
    return dict(_capabilities)


def clear() -> None:
    """Reset the registry (for tests)."""
    _capabilities.clear()


# ---------------------------------------------------------------------------
# Manifest auto-discovery
# ---------------------------------------------------------------------------

_APP = Path(__file__).resolve().parent.parent.parent / "application"


def _discover_manifests() -> dict[str, Path]:
    """Scan ``application/`` for ``app.yaml`` files with a known ``kind:``.

    Returns ``{metadata_name: path}`` for every manifest whose
    ``kind`` is one of Agent, Pipeline, or Workflow.
    """
    discovered: dict[str, Path] = {}
    for path in sorted(_APP.rglob("app.yaml")):
        try:
            with open(path) as f:
                raw = yaml.safe_load(f)
        except Exception:
            logger.warning("manifest_unreadable", path=str(path), exc_info=True)
            continue

        if not isinstance(raw, dict):
            continue

        kind = raw.get("kind")
        if kind not in _KNOWN_KINDS:
            continue

        metadata = raw.get("metadata") or {}
        name = metadata.get("name", "")
        if not name:
            logger.warning("manifest_missing_name", path=str(path))
            continue

        if name in discovered:
            logger.warning(
                "manifest_duplicate_name",
                name=name,
                existing=str(discovered[name]),
                duplicate=str(path),
            )
            continue

        discovered[name] = path
        logger.debug("manifest_discovered", name=name, kind=kind, path=str(path))

    return discovered


# ---------------------------------------------------------------------------
# Shell wiring — routers and CLI groups that reference discovered manifests
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ShellWiring:
    """Maps a manifest name to the shell delivery layer (routers + CLI).

    ``manifest_name`` is the ``metadata.name`` from a discovered YAML.
    If ``manifest_name`` is ``None``, this is a shell-only capability
    (e.g. ``agents``, ``events``) with no backing manifest.
    """

    name: str
    manifest_name: str | None = None
    router_refs: tuple[str, ...] = field(default_factory=tuple)
    cli_ref: str | None = None


def _shell_wiring() -> list[_ShellWiring]:
    """Shell delivery wiring — routers and CLI groups.

    Entries with ``manifest_name`` are merged with an auto-discovered
    manifest.  Entries without are registered as standalone capabilities.

    To add a new agent that has no API routes or CLI: do nothing here.
    Just create an ``app.yaml`` under ``application/`` — it will be
    auto-discovered.

    To wire an existing manifest to API routes or CLI, add one entry
    whose ``manifest_name`` matches the manifest's ``metadata.name``.
    """
    return [
        _ShellWiring(
            name="agents",
            router_refs=("remi.shell.api.chat:router",),
        ),
        _ShellWiring(
            name="portfolio",
            router_refs=(
                "remi.application.portfolio.api:managers_router",
                "remi.application.portfolio.api:owners_router",
                "remi.application.portfolio.api:properties_router",
                "remi.application.portfolio.api:units_router",
            ),
            cli_ref="remi.application.portfolio.cli:cli_group",
        ),
        _ShellWiring(
            name="operations",
            router_refs=(
                "remi.application.operations.api:leases_router",
                "remi.application.operations.api:maintenance_router",
                "remi.application.operations.api:tenants_router",
                "remi.application.operations.api:actions_router",
                "remi.application.operations.api:notes_router",
            ),
            cli_ref="remi.application.operations.cli:cli_group",
        ),
        _ShellWiring(
            name="intelligence",
            router_refs=(
                "remi.application.intelligence.api:dashboard_router",
                "remi.application.intelligence.api:search_router",
                "remi.application.intelligence.api:knowledge_router",
                "remi.application.intelligence.api:events_router",
                "remi.application.intelligence.api:ontology_router",
            ),
            cli_ref="remi.application.intelligence.cli:cli_group",
        ),
        _ShellWiring(
            name="ingestion",
            router_refs=("remi.application.ingestion.api:router",),
            cli_ref="remi.application.ingestion.cli:cli_group",
        ),
        _ShellWiring(
            name="events",
            router_refs=(
                "remi.application.events.api:router",
                "remi.application.events.ws:router",
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Registration — merge discovery + wiring
# ---------------------------------------------------------------------------

_registered = False


def ensure_capabilities_registered() -> None:
    """Discover manifests, merge shell wiring, and register everything.

    Safe to call multiple times — only the first call does work.
    """
    global _registered  # noqa: PLW0603
    if _registered:
        return

    discovered = _discover_manifests()

    wiring_by_manifest: dict[str, _ShellWiring] = {}
    standalone_wiring: list[_ShellWiring] = []
    for w in _shell_wiring():
        if w.manifest_name is not None:
            wiring_by_manifest[w.manifest_name] = w
        else:
            standalone_wiring.append(w)

    for manifest_name, path in discovered.items():
        wiring = wiring_by_manifest.pop(manifest_name, None)
        if wiring is not None:
            cap = CapabilityDescriptor(
                name=wiring.name,
                manifest=path,
                manifest_name=manifest_name,
                router_refs=wiring.router_refs,
                cli_ref=wiring.cli_ref,
            )
        else:
            cap = CapabilityDescriptor(name=manifest_name, manifest=path)
        register(cap)

    for manifest_name, wiring in wiring_by_manifest.items():
        logger.warning(
            "shell_wiring_unmatched",
            wiring_name=wiring.name,
            expected_manifest=manifest_name,
        )

    for w in standalone_wiring:
        register(
            CapabilityDescriptor(
                name=w.name,
                router_refs=w.router_refs,
                cli_ref=w.cli_ref,
            )
        )

    _registered = True
