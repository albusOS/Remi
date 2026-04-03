"""tools — RE agent capabilities (conversational agent tools).

Generic capabilities (sandbox, http, memory, vectors, delegation, trace,
registry) live in ``agent/tools/``.  This package holds real-estate-specific
tool registrations and the ``register_all_tools`` aggregator that the
container calls at startup.
"""

from __future__ import annotations

from remi.agent.tools.http import register_http_tools
from remi.agent.tools.memory import register_memory_tools
from remi.agent.tools.sandbox import register_sandbox_tools
from remi.agent.tools.trace import register_trace_tools
from remi.agent.tools.vectors import register_vector_tools
from remi.agent.types import ToolRegistry
from remi.agent.documents.types import DocumentStore
from remi.agent.graph.adapters.bridge import BridgedKnowledgeGraph
from remi.agent.graph.stores import MemoryStore
from remi.domain.ingestion.documents.pipeline import DocumentIngestService
from remi.agent.observe.types import TraceStore
from remi.domain.core.portfolio.protocols import PropertyStore
from remi.agent.sandbox.types import Sandbox
from remi.domain.intelligence.search.service import SearchService
from remi.agent.signals.persistence.stores import SignalStore
from remi.domain.tools.actions import register_action_tools
from remi.domain.tools.documents import register_document_tools
from remi.domain.tools.ontology import register_knowledge_graph_tools
from remi.domain.tools.search import register_search_tools
from remi.agent.vectors.types import Embedder, VectorStore


def register_all_tools(
    registry: ToolRegistry,
    *,
    knowledge_graph: BridgedKnowledgeGraph,
    document_store: DocumentStore,
    property_store: PropertyStore,
    memory_store: MemoryStore,
    signal_store: SignalStore,
    vector_store: VectorStore,
    embedder: Embedder,
    trace_store: TraceStore,
    sandbox: Sandbox,
    search_service: SearchService,
    api_base_url: str,
    document_ingest: DocumentIngestService | None = None,
) -> None:
    """Phase-1 tool registration (before chat_agent exists).

    Generic capabilities from ``agent/tools/`` plus RE-specific tools
    from ``tools/``.
    """
    # Generic
    register_sandbox_tools(registry, sandbox=sandbox)
    register_http_tools(registry, api_base_url=api_base_url)
    register_memory_tools(registry, memory_store=memory_store)
    register_vector_tools(registry, vector_store=vector_store, embedder=embedder)
    register_trace_tools(registry, trace_store=trace_store)

    # RE-specific
    register_knowledge_graph_tools(
        registry, knowledge_graph=knowledge_graph, signal_store=signal_store
    )
    register_document_tools(
        registry, document_store=document_store, document_ingest=document_ingest
    )
    register_action_tools(
        registry, property_store=property_store, knowledge_graph=knowledge_graph
    )
    register_search_tools(registry, search_service=search_service)
