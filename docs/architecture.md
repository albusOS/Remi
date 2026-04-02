# REMI Architecture

## Philosophy

REMI is a property intelligence platform built for autonomous operation.
Every structural decision flows from three principles:

1. **Unix-inspired hierarchy.** Files and folders are infrastructure, not
   cosmetics. The directory tree is the primary documentation. Names describe
   what things *are*, not which layer they sit in. An `ls` at any level tells
   you what exists and where the boundaries fall.

2. **Inside-out construction.** Build from the innermost primitives outward.
   Pure types first, then capabilities, then domain, then composition.
   Dependencies flow strictly inward — never outward, never sideways.

3. **Honest decoupling.** The line between "generic capability" and
   "real estate product" is visible in a single `ls`. Everything above
   `portfolio/` could power any domain. Everything from `portfolio/` down
   is property management. No half-measures.

---

## The Two Halves

```
src/remi/

  ┌─────────────────────────────────────────────────────────────┐
  │  Domain-Agnostic Capabilities                               │
  │                                                             │
  │  types/     Pure vocabulary — zero deps, no I/O             │
  │  db/        Database engine + table metadata                │
  │  llm/       LLM provider ports + adapters                   │
  │  vectors/   Embedding ports + adapters + pipeline            │
  │  sandbox/   Code execution ports + adapters                  │
  │  observe/   Structured logging + tracing                     │
  │  signals/   Signal types, stores, engine, composite          │
  │  graph/     Knowledge graph types, bridge, retriever         │
  │  documents/ Document types, stores, parsers                  │
  │  agent/     LLM runtime: loop, tools, context, perception    │
  ├─────────────────────────────────────────────────────────────┤
  │  Real Estate (the product)                                   │
  │                                                             │
  │  portfolio/   Entity DTOs + protocols + business rules       │
  │  stores/      RE persistence adapters                        │
  │  queries/     RE query services (dashboard, rent roll, …)    │
  │  evaluators/  RE signal producers (delinquency, lease, …)    │
  │  ingestion/   RE inbound data pipeline                       │
  │  ontology/    RE knowledge graph schema                      │
  │  search/      RE-aware hybrid search + pattern detection     │
  │  tools/       RE agent capabilities                          │
  │  configs/     RE agent YAML manifests                        │
  ├─────────────────────────────────────────────────────────────┤
  │  Composition Root                                            │
  │                                                             │
  │  shell/     DI container, settings, API mountpoint, CLI      │
  └─────────────────────────────────────────────────────────────┘
```

---

## Domain-Agnostic Capabilities

Each is a self-contained subsystem. Could power any domain.
Owns its types + ports + adapters together.

### `types/` — Pure vocabulary

No I/O. No deps beyond pydantic/stdlib. If you deleted everything else,
`types/` would still compile.

```
types/
  ids.py          ID generation — deterministic, collision-free
  clock.py        UTC-aware time source (injectable for tests)
  errors.py       Base exception hierarchy
  enums.py        Cross-cutting enumerations (e.g. Severity)
  result.py       Result[T] / error-carrying return types
  text.py         String utilities (slugify, truncate, normalize)
```

### `db/` — Database engine

```
db/
  engine.py       SQLAlchemy async engine factory, session factory
  tables.py       Table metadata (schema definitions, not models)
```

### `llm/` — LLM providers

```
llm/
  types.py        LLMProvider ABC, LLMRequest/Response, TokenUsage
  openai.py       OpenAI adapter
  anthropic.py    Anthropic adapter
  gemini.py       Gemini adapter
  factory.py      build_provider_factory() — selects adapter from settings
```

### `vectors/` — Embedding subsystem

```
vectors/
  types.py        Embedder, VectorStore, EmbeddingRecord, SearchResult ABCs
  embedder.py     Embedding implementation + build_embedder()
  store.py        InMemoryVectorStore
  pipeline.py     EmbeddingPipeline — batch embed + index
  tokens.py       Token counting, truncation utilities
```

### `sandbox/` — Code execution

```
sandbox/
  types.py        Sandbox, SandboxSession, ExecResult ABCs
  local.py        LocalSandbox — subprocess-based execution
  docker.py       DockerSandbox — container-based execution
  policy.py       Subprocess env builder, dangerous-command blocklist
  bridge.py       remi_data.py source injected into every sandbox session
  factory.py      build_sandbox(settings) — selects backend
```

### `observe/` — Observability

```
observe/
  types.py        Tracer, TraceStore, Span
  logging.py      structlog configuration, configure_logging()
  tracer.py       Trace context, span helpers
  mem.py          InMemoryTraceStore
```

### `signals/` — Signal detection framework

```
signals/
  types.py        Signal, SignalDefinition, DomainRulebook, Policy, etc.
  stores.py       SignalStore, FeedbackStore, HypothesisStore ABCs
  engine.py       EntailmentEngine (generic dispatch on RuleCondition)
  composite.py    CompositeProducer, build_signal_pipeline
  mem.py          InMemorySignalStore, InMemoryFeedbackStore, InMemoryHypothesisStore
```

### `graph/` — Knowledge graph

```
graph/
  types.py        KnowledgeGraph, Entity, Relationship, KnowledgeLink ABCs
  bridge.py       BridgedKnowledgeGraph
  retriever.py    GraphRetriever (vector + graph fusion)
  mem.py          InMemoryKnowledgeStore
```

### `documents/` — Document management

```
documents/
  types.py        Document, DocumentStore ABCs
  parsers.py      Generic file parsing (CSV, XLSX)
  mem.py          InMemoryDocumentStore
  pg.py           PostgresDocumentStore
```

### `agent/` — LLM runtime

The agent is the LLM actor. It owns the execution engine, conversation
management, and **perception** (context building). Context building is
domain-agnostic — it operates on generic types (Signal, KnowledgeGraph,
DomainRulebook) to assemble what the agent knows before reasoning.

```
agent/
  types.py              ToolRegistry, ToolDefinition, Message, ChatSession ABCs
  runner.py             ChatAgentService
  loop.py               Agent loop
  node.py               AgentNode
  llm_bridge.py         Domain ↔ LLM message translation
  tool_executor.py      Dispatches tool calls
  thread.py             Conversation history
  thread_compression.py Long-thread summarization
  intent.py             Intent classification
  context.py            RuntimeContext (deps, params)
  context_builder.py    ContextBuilder + ContextFrame (generic perception)
  context_rendering.py  render_domain_context, render_active_signals, render_graph_context
  retry.py              LLM retry policy
  base.py               Agent base class
  config.py             AgentConfig, PhaseConfig
  registry.py           InMemoryToolRegistry
  mem.py                InMemoryChatSessionStore, InMemoryMemoryStore
```

**Two agent modes:**

- **Conversational agents** run inside the REMI process. They call domain
  services via `tools/`. Their tool registry is the capability manifest.

- **Code-first agents** run as isolated subprocesses inside `sandbox/`.
  They call REMI through `remi_data` (a stdlib HTTP bridge). The API
  surface is their tool registry.

---

## Real Estate (the product)

Everything below is property-management-specific.
Replace this section to build a healthcare or logistics product.

### `portfolio/` — Entity definitions

Thin. Just entity DTOs, narrow repository protocols, and pure
business rule functions. ~3 files.

```
portfolio/
  models.py       Property, Unit, Tenant, Lease, Manager, Portfolio, etc.
  protocols.py    Narrow repository ABCs (LeaseRepository, UnitRepository, …)
  rules.py        is_occupied, loss_to_lease, is_below_market, etc.
```

### `stores/` — RE persistence adapters

Implement the protocols defined in `portfolio/`.

```
stores/
  mem.py          InMemoryPropertyStore
  pg.py           PostgresPropertyStore
  rollups.py      InMemoryRollupStore, PostgresRollupStore
  factory.py      build_property_store, build_rollup_store
```

### `queries/` — RE query services

All the analytical views and data aggregation over portfolio state.

```
queries/
  dashboard.py    PortfolioOverview, DelinquencyBoard, VacancyTracker
  rent_roll.py    RentRollResult
  leases.py       ExpiringLeasesResult
  properties.py   PropertyDetail, PropertyListItem
  portfolios.py   Portfolio aggregations
  maintenance.py  MaintenanceQueryService
  managers.py     ManagerReviewService, ManagerRanking
  snapshots.py    SnapshotService (capture + query)
  metrics.py      Unit-level metric helpers (shared across queries + evaluators)
  auto_assign.py  Manager auto-assignment
```

### `evaluators/` — RE signal producers

Derive signals from portfolio state. Each evaluator is a
`SignalProducer` that reads from stores and emits signals.

```
evaluators/
  delinquency.py  eval_manager_delinquency
  existence.py    eval_exists, eval_in_legal_track
  lease.py        eval_breach_detected, eval_manager_lease_cliff
  maintenance.py  eval_manager_maintenance_backlog
  portfolio.py    eval_below_percentile, eval_concentration_risk
  threshold.py    eval_unit_threshold
  trend.py        eval_consistent_direction, eval_declining_consecutive_periods
  composition.py  CompositionProducer
  statistical.py  StatisticalProducer
  base.py         MakeSignalFn, EntailmentResult, signal_id
```

### `ingestion/` — RE inbound data pipeline

The full inbound flow: parse → extract → persist → enrich.
All adapters and event types are RE-specific.

```
ingestion/
  pipeline.py     DocumentIngestService (full inbound flow)
  service.py      IngestionService (schema-driven extraction)
  engine.py       apply_events (canonical event loop)
  seed.py         SeedService
  enrichment.py   EnrichFn, parse_enricher_output
  llm_adapters.py make_classify_fn, make_enrich_fn
  managers.py     ManagerResolver
  generic.py      Fallback for unrecognized reports
  adapters/
    appfolio/     AppFolio-specific parsing
      adapter.py
      detector.py
      parsers.py
      schema.py
    registry.py   Source adapter dispatch
```

### `ontology/` — RE knowledge graph schema

```
ontology/
  schema.py       REMI domain schema + seed_knowledge_graph
  remote.py       RemoteKnowledgeGraph (HTTP client for sandbox)
```

### `search/` — RE-aware search

```
search/
  service.py      SearchService (RE-aware hybrid search)
  pattern.py      Cross-property pattern detection
  graduation.py   Hypothesis → codified knowledge
```

### `tools/` — RE agent capabilities

Conversational agent capabilities. Each tool wraps an RE service
for the agent to call.

```
tools/
  __init__.py     register_all_tools
  ontology.py
  documents.py
  search.py
  vectors.py
  sandbox.py
  actions.py
  memory.py
  trace.py
  http.py
  workflows.py
  delegation.py
  snapshots.py
```

### `configs/` — RE agent YAML manifests

```
configs/
  director/app.yaml
  researcher/app.yaml
  knowledge_enricher/app.yaml
  report_classifier/app.yaml
  action_planner/app.yaml
```

---

## Shell — Composition Root

The only place that knows about all packages. Wires everything together.

```
shell/
  config/
    container.py      DI Container — calls build_*() from owning modules
    settings.py       Pydantic settings — env vars, feature flags
    domain.yaml       Source of truth for signal thresholds, rules, domain config
  api/
    main.py           Mounts all routers — no routes defined here
    dependencies.py   FastAPI DI (delegates to Container)
    middleware.py     Auth, logging, timing
    error_handler.py  Unified error → HTTP response mapping
    schemas.py        HTTP-only envelope types
    properties/       Portfolio resource routes
    units/
    leases/
    tenants/
    managers/
    portfolios/
    maintenance/
    dashboard/
    actions/
    notes/
    signals/          Intelligence routes
    ontology/
    search_routes/
    documents/
    seed/
    agents/           Agent routes
    realtime/
  cli/
    main.py           Mounts all CLI commands — no commands defined here
    shared.py         get_container, json_out helpers
    banner.py         Startup banner
    live_display.py   Textual live display utility
    http.py
    properties/
    dashboard.py
    documents.py
    seed.py
    ontology.py
    search.py
    trace.py
    vectors.py
    agents/
    bench.py
    research.py
```

---

## Dependency Flow

```
shell/ ──→ everything (composition root)
tools/ ──→ queries/, evaluators/, ingestion/, ontology/, search/
configs/ ──→ agent/
queries/ ──→ portfolio/, stores/
evaluators/ ──→ portfolio/, stores/, signals/
ingestion/ ──→ portfolio/, stores/, documents/, signals/
ontology/ ──→ graph/
search/ ──→ graph/, vectors/, signals/
agent/ ──→ signals/, graph/, vectors/, llm/, sandbox/, observe/
portfolio/ ──→ types/
stores/ ──→ portfolio/, db/
signals/ ──→ types/
graph/ ──→ vectors/, types/
documents/ ──→ types/
llm/ ──→ types/
vectors/ ──→ types/
sandbox/ ──→ types/
observe/ ──→ types/
db/ ──→ types/
types/ ──→ nothing
```

---

## Key Decisions

1. **`agent/` owns context building.** `ContextBuilder`, `ContextFrame`,
   `context_rendering`, and `GraphRetriever` are domain-agnostic perception.
   They operate on generic types (Signal, KnowledgeGraph, DomainRulebook).

2. **`agent/` owns `llm/` as a peer capability.** LLM providers are the
   agent's voice. Every framework puts models inside the agent package.

3. **`portfolio/` is thin.** Just entity DTOs, repository protocols, and
   pure business rule functions. ~3 files.

4. **`queries/` and `evaluators/` are peers** at the same level. They both
   analyze portfolio data — queries output read-models, evaluators output
   signals.

5. **`stores/` is separate from `portfolio/`.** Persistence adapters
   implement protocols. Entity definitions don't know how they're stored.

6. **`ingestion/` is a complete vertical.** Parse → extract → persist →
   enrich. All wired to RE-specific types. Self-contained.

7. **`shell/api/` owns all routes. `shell/cli/` owns all commands.** HTTP
   and terminal are interface concerns — not co-located inside domain packages.

8. **`vectors/pipeline.py` needs decoupling.** Currently imports
   `PropertyStore` directly. Should accept a generic "entity text extractor"
   protocol instead.

9. **The generic/RE boundary is visible in `ls`.** Everything above
   `portfolio/` is generic. Everything from `portfolio/` through `configs/`
   is real estate.

---

## Hexagonal Boundary — The One Rule

```
Generic code                               Infrastructure code
────────────                              ──────────────────
imports ports (ABCs/types.py)    ←ports→  implements ports
never imports psycopg2                    imports psycopg2
never imports openai                      imports openai
never imports docker                      imports docker
```

`shell/config/container.py` is the *only* file that knows both sides.

---

## How to Handle Unknowns

### 1. Which half does it belong to?

| Question | Half |
|----------|------|
| Could this work for healthcare/logistics? | Generic capability |
| Does it mention Property, Unit, Tenant, Lease? | Real estate |

### 2. Which package?

| Concept | Package |
|---------|---------|
| Pure types, no I/O | `types/` |
| Database machinery | `db/` |
| LLM provider interaction | `llm/` |
| Embedding, vector search | `vectors/` |
| Code execution | `sandbox/` |
| Logging, tracing | `observe/` |
| Signal framework | `signals/` |
| Knowledge graph framework | `graph/` |
| Document framework | `documents/` |
| LLM runtime, context, perception | `agent/` |
| RE entities, protocols, rules | `portfolio/` |
| RE persistence | `stores/` |
| RE analytical views | `queries/` |
| RE signal producers | `evaluators/` |
| RE inbound data | `ingestion/` |
| RE graph schema | `ontology/` |
| RE search | `search/` |
| RE agent tools | `tools/` |
| RE agent configs | `configs/` |
| Wiring, DI, HTTP, CLI | `shell/` |

### 3. Factory pattern

Each module owns its factory: `build_*()` lives in the module that
defines the thing. `container.py` calls factories — never inlines assembly.

### 4. When genuinely unsure

Place the file in the most likely package with a comment:
```python
# PLACEMENT: provisional — belongs in X once Y exists
```
Never place uncertain code in `types/` to avoid the decision.
