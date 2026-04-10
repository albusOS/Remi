"""Workspace isolation — the kernel boundary for multi-tenant agent execution.

A ``WorkspaceContext`` is the isolation unit for the agent OS. Every agent
run executes within exactly one workspace. The workspace scopes:

- **Memory** — reads/writes are prefixed by workspace_id
- **Tools** — only tools registered for this workspace are resolvable
- **Delegation** — cross-workspace delegation requires explicit edges
- **Credentials** — each workspace has its own credential store
- **Events** — domain events carry workspace_id for routing

The kernel defines the primitives. The shell assembles them into concrete
workspaces at startup — one per business division (property management,
maintenance services, supply store, finance, etc.).

A workspace is NOT a tenant in the SaaS sense (one customer = one workspace).
It's a bounded operational context: one division's agents, tools, data, and
credentials. A single company may have 5 workspaces. The exec's agents can
reach across workspace boundaries via declared delegation edges.

Usage::

    from remi.agent.isolation import WorkspaceContext, WorkspaceRegistry

    ctx = registry.get("maintenance-llc")
    ctx.workspace_id        # WorkspaceId("maintenance-llc")
    ctx.identity_store      # agents in this workspace
    ctx.credential_store    # secrets for this workspace
    ctx.tool_namespace      # tools scoped to this workspace
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from remi.agent.identity import CredentialStore, IdentityStore
from remi.types.ids import DEFAULT_WORKSPACE, WorkspaceId


@dataclass(frozen=True)
class WorkspaceContext:
    """Immutable isolation context for a single workspace.

    Every agent run receives one of these. The runtime uses it to scope
    memory access, tool resolution, credential lookups, and delegation
    validation. Inner-ring code (agent loop, tool executor) never sees
    raw store references — only this context.
    """

    workspace_id: WorkspaceId = DEFAULT_WORKSPACE

    identity_store: IdentityStore | None = None
    credential_store: CredentialStore | None = None

    tool_namespace: str = ""

    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def memory_prefix(self) -> str:
        """Prefix for all memory keys in this workspace.

        Ensures workspace-level isolation even when sharing a single
        ``MemoryStore`` backend. Format: ``ws:{workspace_id}:``.
        Returns empty string for the default workspace (backward compat).
        """
        if self.workspace_id == DEFAULT_WORKSPACE:
            return ""
        return f"ws:{self.workspace_id}:"

    @property
    def is_default(self) -> bool:
        return self.workspace_id == DEFAULT_WORKSPACE


class WorkspaceRegistry(abc.ABC):
    """Port for resolving workspace contexts at runtime.

    The shell builds and registers workspaces at startup. The runtime
    resolves them by id when an agent run begins.
    """

    @abc.abstractmethod
    def get(self, workspace_id: WorkspaceId) -> WorkspaceContext | None:
        """Return the workspace context, or ``None`` if unknown."""

    @abc.abstractmethod
    def list_workspaces(self) -> list[WorkspaceId]:
        """Return all registered workspace ids."""

    @abc.abstractmethod
    def register(self, ctx: WorkspaceContext) -> None:
        """Register a workspace context. Overwrites if already present."""


class InMemoryWorkspaceRegistry(WorkspaceRegistry):
    """Simple dict-backed workspace registry for single-process deployments."""

    def __init__(self) -> None:
        self._workspaces: dict[WorkspaceId, WorkspaceContext] = {}

    def get(self, workspace_id: WorkspaceId) -> WorkspaceContext | None:
        return self._workspaces.get(workspace_id)

    def list_workspaces(self) -> list[WorkspaceId]:
        return list(self._workspaces.keys())

    def register(self, ctx: WorkspaceContext) -> None:
        self._workspaces[ctx.workspace_id] = ctx
