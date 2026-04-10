"""Agent identity — the kernel primitive for agent credentials and access scope.

Each agent in the workforce has a stable identity that maps to:
- External credentials (OAuth tokens, API keys) resolved at runtime
- A workspace scope that constrains memory, tools, and delegation
- An optional human principal (the director this agent acts for)

The kernel defines the protocol and types. Implementations live in
``application/`` or ``shell/`` — the kernel never touches real secrets.

Usage::

    from remi.agent.identity import AgentIdentity, CredentialStore

    identity = AgentIdentity(
        agent_name="maintenance_director",
        workspace_id=WorkspaceId("maintenance-llc"),
        principal="jake.kraus@company.com",
        credential_refs={"servicem8": "servicem8-maint-oauth", "gmail": "gmail-jake"},
    )

    # At runtime, the credential store resolves refs to actual secrets
    token = await cred_store.resolve("servicem8-maint-oauth")
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from remi.types.ids import DEFAULT_WORKSPACE, WorkspaceId


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    """Stable identity for a named agent within a workspace.

    ``credential_refs`` maps logical service names (``"gmail"``,
    ``"servicem8"``, ``"xero"``) to opaque secret reference keys that
    the ``CredentialStore`` resolves at runtime.  The identity itself
    never holds raw secrets.

    ``principal`` is the human this agent acts on behalf of — used for
    audit trails, email scoping, and access control decisions.
    """

    agent_name: str
    workspace_id: WorkspaceId = DEFAULT_WORKSPACE
    principal: str = ""
    credential_refs: dict[str, str] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        """Workspace-qualified agent name for cross-workspace references."""
        return f"{self.workspace_id}:{self.agent_name}"


@dataclass(frozen=True, slots=True)
class ResolvedCredential:
    """A resolved secret — short-lived, never persisted in memory or logs."""

    ref: str
    service: str
    token: str
    expires_at: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class CredentialStore(abc.ABC):
    """Port for resolving credential references to actual secrets.

    Implementations may back onto environment variables, Vault, AWS
    Secrets Manager, or a database — the kernel doesn't care.  The
    contract is: give me a ref string, I give you a token.

    Credential stores are workspace-scoped: a store instance serves
    one workspace and will refuse refs that belong to another.
    """

    @abc.abstractmethod
    async def resolve(self, ref: str) -> ResolvedCredential | None:
        """Resolve a credential reference to a live secret.

        Returns ``None`` if the ref is unknown or expired.
        """

    @abc.abstractmethod
    async def resolve_for_agent(
        self,
        identity: AgentIdentity,
        service: str,
    ) -> ResolvedCredential | None:
        """Resolve a credential for a specific agent + service.

        Looks up the agent's ``credential_refs[service]`` and resolves it.
        Returns ``None`` if the agent has no ref for that service.
        """

    @abc.abstractmethod
    async def list_services(self, identity: AgentIdentity) -> list[str]:
        """List the service names this agent has credentials for."""


class IdentityStore(abc.ABC):
    """Port for persisting and retrieving agent identities.

    The identity store is the authority for which agents exist in a
    workspace, what credentials they hold, and who they act for.
    """

    @abc.abstractmethod
    async def get(
        self,
        agent_name: str,
        workspace_id: WorkspaceId,
    ) -> AgentIdentity | None: ...

    @abc.abstractmethod
    async def list_agents(
        self,
        workspace_id: WorkspaceId,
    ) -> list[AgentIdentity]: ...

    @abc.abstractmethod
    async def upsert(self, identity: AgentIdentity) -> None: ...

    @abc.abstractmethod
    async def delete(
        self,
        agent_name: str,
        workspace_id: WorkspaceId,
    ) -> bool: ...
