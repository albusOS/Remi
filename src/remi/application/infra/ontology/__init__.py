"""Ontology — knowledge graph bridge, schema, and seeding.

Public API::

    from remi.application.infra.ontology import build_knowledge_graph, load_domain_yaml
"""

from remi.application.infra.ontology.bridge import build_knowledge_graph
from remi.application.infra.ontology.schema import load_domain_yaml
from remi.application.infra.ontology.seed import seed_knowledge_graph

__all__ = [
    "build_knowledge_graph",
    "load_domain_yaml",
    "seed_knowledge_graph",
]
