"""Domain — real estate product intelligence.

Organized as CCCC (Core, Context, Category, Command):

    core/           Internal plumbing — entity models, protocols, persistence, ontology
    monitoring/     Situation awareness — signal evaluation + time-series snapshots
    ingestion/      Inbound data — document extraction, embedding, seeding
    intelligence/   Queries and search — read-model aggregation + hybrid search
    tools/          View layer — agent-facing tool registrations
    agents/         YAML manifests for named agent configurations
"""
