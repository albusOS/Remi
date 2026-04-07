"""Workforce — declarative agent network topology.

A workforce manifest describes the complete graph of agents, their
relationships, and the tools they share. It is the data model that a
visual canvas compiles to and the runtime reads from.

The workforce is assembled at startup from individual agent manifests:
each agent's ``delegates_to:`` edges form the delegation graph, each
agent's ``tools:`` form the capability surface, and each agent's
``runtime:`` form the execution topology.

Example workforce assembly::

    workforce = Workforce.from_manifests(["director", "researcher", "action_planner"])

    workforce.agents          # {name: AgentDescriptor}
    workforce.delegation_graph  # {parent: [child, ...]}
    workforce.tool_surface      # {agent: [tool_name, ...]}

A future ``kind: Workforce`` YAML manifest will allow declaring the
entire network in one file with overrides — but today the workforce
is computed from individual ``kind: Agent`` manifests.
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import Any

import structlog
import yaml
from pydantic import BaseModel, ConfigDict, Field

from remi.agent.config import AgentConfig, DelegateRef
from remi.agent.runtime.config import RuntimeConfig
from remi.agent.workflow.registry import get_manifest_path

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Typed manifest model — validates raw YAML before extraction
# ---------------------------------------------------------------------------


@unique
class Audience(StrEnum):
    """Who consumes this agent's output."""

    USER = "user"
    INTERNAL = "internal"
    SYSTEM = "system"


class ManifestMetadata(BaseModel):
    """The ``metadata:`` section of an agent manifest."""

    model_config = ConfigDict(extra="allow", frozen=True)

    name: str = ""
    version: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    domain: str = ""
    audience: Audience = Audience.INTERNAL
    chat: bool = False
    primary: bool = False


class ManifestModule(BaseModel):
    """A single entry in the ``modules:`` list of a manifest."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str = ""
    kind: str = ""
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class AgentManifest(BaseModel):
    """Typed representation of a ``kind: Agent`` YAML manifest.

    Validates the top-level structure so that downstream code never
    operates on raw ``dict[str, Any]``.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    apiVersion: str = "remi/v1"  # noqa: N815
    kind: str = "Agent"
    metadata: ManifestMetadata = Field(default_factory=ManifestMetadata)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    modules: list[ManifestModule] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AgentDescriptor — the typed summary consumed by the rest of the system
# ---------------------------------------------------------------------------


class AgentDescriptor(BaseModel):
    """Summary of a registered agent's capabilities and topology."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    tools: tuple[str, ...] = ()
    delegates_to: tuple[DelegateRef, ...] = ()
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    audience: Audience = Audience.INTERNAL
    chat: bool = False
    primary: bool = False


# ---------------------------------------------------------------------------
# Workforce — the network read model
# ---------------------------------------------------------------------------


class Workforce(BaseModel):
    """The complete agent network — agents, edges, and tool surfaces.

    Built from registered manifests at startup. Provides the read model
    that the delegation tool, the canvas UI, and observability dashboards
    consume to understand the agent topology.
    """

    model_config = ConfigDict(frozen=True)

    agents: dict[str, AgentDescriptor] = Field(default_factory=dict)

    @property
    def delegation_graph(self) -> dict[str, list[str]]:
        """Parent -> children adjacency list."""
        return {
            name: [d.agent for d in desc.delegates_to]
            for name, desc in self.agents.items()
            if desc.delegates_to
        }

    @property
    def tool_surface(self) -> dict[str, tuple[str, ...]]:
        """Agent name -> tool names it has access to."""
        return {
            name: desc.tools
            for name, desc in self.agents.items()
        }

    def get_delegates(self, agent_name: str) -> dict[str, str]:
        """Return {child_name: description} for a specific parent agent."""
        desc = self.agents.get(agent_name)
        if desc is None:
            return {}
        return {d.agent: d.description for d in desc.delegates_to}

    def get_delegate_ref(self, parent: str, child: str) -> DelegateRef | None:
        """Return the ``DelegateRef`` edge from *parent* to *child*, or ``None``."""
        desc = self.agents.get(parent)
        if desc is None:
            return None
        for d in desc.delegates_to:
            if d.agent == child:
                return d
        return None

    def get_agent(self, name: str) -> AgentDescriptor | None:
        """Return the descriptor for a named agent, or ``None``."""
        return self.agents.get(name)

    @property
    def chat_agents(self) -> list[AgentDescriptor]:
        """Return descriptors for user-facing chat agents, primary first."""
        result = [d for d in self.agents.values() if d.chat]
        result.sort(key=lambda d: (not d.primary, d.name))
        return result

    @classmethod
    def from_manifests(cls, agent_names: list[str]) -> Workforce:
        """Build a workforce from an explicit list of agent manifest names."""
        agents: dict[str, AgentDescriptor] = {}
        for name in agent_names:
            try:
                desc = _load_agent_descriptor(name)
                agents[name] = desc
            except (ValueError, FileNotFoundError):
                logger.warning("workforce_agent_not_found", agent=name)
        return cls(agents=agents)

    @classmethod
    def from_registry(cls) -> Workforce:
        """Build a workforce from all manifests registered at startup."""
        from remi.agent.workflow.registry import all_manifests

        return cls.from_manifests(list(all_manifests()))


def _load_agent_descriptor(agent_name: str) -> AgentDescriptor:
    """Load an AgentDescriptor from a registered manifest with full validation."""
    path = get_manifest_path(agent_name)
    with open(path) as f:
        raw = yaml.safe_load(f)

    manifest = AgentManifest.model_validate(raw)

    agent_config: AgentConfig | None = None
    for module in manifest.modules:
        if module.kind == "agent":
            cfg_data = dict(module.config)
            cfg_data["name"] = agent_name
            agent_config = AgentConfig.from_dict(cfg_data)
            break

    tools: tuple[str, ...] = ()
    delegates: tuple[DelegateRef, ...] = ()
    if agent_config is not None:
        tools = tuple(t.name for t in agent_config.tools)
        delegates = tuple(agent_config.delegates_to)

    return AgentDescriptor(
        name=agent_name,
        description=manifest.metadata.description,
        tools=tools,
        delegates_to=delegates,
        runtime=manifest.runtime,
        audience=manifest.metadata.audience,
        chat=manifest.metadata.chat,
        primary=manifest.metadata.primary,
    )
