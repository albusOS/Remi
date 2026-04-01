"""knowledge.ontology — KnowledgeGraph implementations and schema.

Subpackage containing:
  bridge — BridgedKnowledgeGraph (local in-process, backed by PropertyStore + KnowledgeStore)
  remote — RemoteKnowledgeGraph (HTTP client, used by sandbox processes)
  schema — REMI domain schema definitions and seeding
"""

from remi.knowledge.ontology.bridge import (
    BridgedKnowledgeGraph,
    BridgedOntologyStore,
    CoreTypeBindings,
    build_knowledge_graph,
)
from remi.knowledge.ontology.remote import RemoteKnowledgeGraph, RemoteOntologyStore
from remi.knowledge.ontology.schema import (
    bootstrap_knowledge_graph,
    bootstrap_ontology,
    load_domain_yaml,
    seed_knowledge_graph,
)

__all__ = [
    "BridgedKnowledgeGraph",
    "BridgedOntologyStore",
    "CoreTypeBindings",
    "RemoteKnowledgeGraph",
    "RemoteOntologyStore",
    "bootstrap_knowledge_graph",
    "bootstrap_ontology",
    "build_knowledge_graph",
    "load_domain_yaml",
    "seed_knowledge_graph",
]
