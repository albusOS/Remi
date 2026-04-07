"""Graph — RE world model and domain YAML loading.

``REWorldModel`` wraps ``PropertyStore`` to provide a domain-agnostic
``WorldModel`` interface for the agent kernel.
"""

from remi.agent.signals.tbox import load_domain_yaml
from remi.application.infra.graph.world import REWorldModel, build_re_world_model

__all__ = [
    "REWorldModel",
    "build_re_world_model",
    "load_domain_yaml",
]
