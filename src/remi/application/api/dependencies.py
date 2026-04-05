"""Backward-compatibility shim — dependencies moved to ``remi.shell.api.dependencies``.

Import from ``remi.shell.api.dependencies`` in new code.
"""

from remi.shell.api.dependencies import (  # noqa: F401
    get_auto_assign_service,
    get_chat_agent,
    get_chat_session_store,
    get_container,
    get_dashboard_service,
    get_document_ingest,
    get_document_store,
    get_event_store,
    get_feedback_store,
    get_knowledge_graph,
    get_knowledge_store,
    get_lease_query,
    get_maintenance_query,
    get_manager_review,
    get_portfolio_query,
    get_property_query,
    get_property_store,
    get_provider_factory,
    get_rent_roll_service,
    get_search_service,
    get_seed_service,
    get_settings,
    get_signal_store,
    get_usage_ledger,
)
