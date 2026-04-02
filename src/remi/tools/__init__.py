"""tools — RE agent capabilities (conversational agent tools)."""

from __future__ import annotations

from remi.agent.types import ToolRegistry
from remi.documents.types import DocumentStore
from remi.graph.bridge import BridgedKnowledgeGraph
from remi.graph.stores import MemoryStore
from remi.observe.types import TraceStore
from remi.sandbox.types import Sandbox
from remi.search.service import SearchService
from remi.signals.stores import SignalStore
from remi.portfolio.protocols import PropertyStore
from remi.vectors.types import Embedder, VectorStore

from remi.tools.actions import register_action_tools
from remi.tools.documents import register_document_tools
from remi.tools.http import register_http_tools
from remi.tools.memory import register_memory_tools
from remi.tools.ontology import register_knowledge_graph_tools
from remi.tools.sandbox import register_sandbox_tools
from remi.tools.search import register_search_tools
from remi.tools.trace import register_trace_tools
from remi.tools.vectors import register_vector_tools


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
) -> None:
    """Phase-1 tool registration (before chat_agent exists)."""
    register_knowledge_graph_tools(registry, knowledge_graph=knowledge_graph, signal_store=signal_store)
    register_document_tools(registry, document_store=document_store)
    register_action_tools(registry, property_store=property_store, knowledge_graph=knowledge_graph)
    register_memory_tools(registry, memory_store=memory_store)
    register_sandbox_tools(registry, sandbox=sandbox)
    register_search_tools(registry, search_service=search_service)
    register_http_tools(registry, api_base_url=api_base_url)
    register_trace_tools(registry, trace_store=trace_store)
    register_vector_tools(registry, vector_store=vector_store, embedder=embedder)
