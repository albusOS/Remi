# REMI

AI platform for property management directors. The director's core question: **which of my managers needs my attention, and why?**

## Commands

```bash
uv run pytest tests/ -q              # run all tests
uv run pytest tests/entailment/ -q   # run a specific folder
uv run remi serve --seed             # start API server with demo data
uv run remi onto signals             # show active signals
uv run remi trace list               # recent traces
```

## Tooling Rules

- Always use `uv run` to execute Python — never `python` directly
- Always use `uv add` to add dependencies — never `pip install`
- Never reference `.venv/` paths directly

## Error Handling — Zero Silent Swallows

Every exception must either **propagate** or be **logged at warning+ with
`exc_info=True`**. No other option exists.

**Banned patterns** (will be rejected in review):
- `except Exception: pass` / `except Exception: continue`
- `except SomeError: return None` without a log line
- `except Exception as e: return {"error": str(e)}` without logging
- Bare `except:` — always name the exception type
- Catching broad `Exception` when a narrower type fits (`ValueError`, `TypeError`, `KeyError`, etc.)

**Acceptable patterns:**
- `except ImportError` for optional-dependency guards (must raise or feature-flag)
- `except (KeyboardInterrupt, EOFError)` in CLI interactive loops
- `except Exception` that logs at `warning`/`error` with `exc_info=True` **and** surfaces the failure to the caller (error count, warnings list, or re-raise)

**Batch/pipeline catch-and-continue** must:
1. Log at `warning` with `exc_info=True`
2. Record the failure in a result object the caller can inspect

Use `structlog` for all logging, not `print` or `logging` directly.

## Type Safety — No `Any`, No Untyped `dict`

**Banned in new code:**
- `dict[str, Any]` as a function return or parameter — use a Pydantic model or TypedDict
- `-> Any` return annotations — be explicit
- `list[dict]` — model the items
- Returning `None` to mean "something failed" — raise an error instead

**When touching existing `Any`/`dict` code**, narrow the type if feasible.
At minimum, don't introduce new ones.

## Tests

- Only write tests for meaningful behavior — not implementation details or happy-path tautologies
- Tests should cover real failure modes and edge cases worth caring about
- Ask before writing tests if the value isn't obvious

## Architecture: Four Layers

```
Layer 1 — Facts       stores/          PropertyStore, KnowledgeStore, DocumentStore, SignalStore, VectorStore, TraceStore, MemoryStore, ChatStore, SnapshotStore
Layer 2 — Domain      config/          domain.yaml (rulebook), ontology (schema), container (DI), settings
Layer 3 — Signals     services/        entailment engine → SignalStore; pattern detector → hypotheses; domain services (dashboard, manager review, ingestion, queries)
Layer 4 — Interface   api/, cli/       FastAPI routes + WebSocket, Typer CLI, agent loop, frontend
```

**When creating or moving code, say which layer it belongs to before placing it.**

Key constraint: the LLM agent does NOT detect signals — the entailment engine does.
The LLM's job is abductive reasoning: explain, connect, recommend, codify.

## Key Files

| File | Role |
|------|------|
| `src/remi/config/domain.yaml` | Source of truth for signal definitions, thresholds, rules, policies, causal chains, workflows |
| `src/remi/config/container.py` | DI container — wires all stores, services, agents, tools |
| `src/remi/agents/director/app.yaml` | Director agent — fast Q&A, system prompt, tools |
| `src/remi/agents/researcher/app.yaml` | Researcher agent — deep analysis, sandbox, phased protocol |
| `src/remi/agent/node.py` | AgentNode — config-driven think-act-observe loop |
| `src/remi/knowledge/entailment/engine.py` | Entailment engine — evaluates rules, produces signals |
| `src/remi/knowledge/ingestion/schema.py` | Declarative report schemas + unified `ingest_report()` loop |
| `src/remi/knowledge/ingestion/managers.py` | Manager classification (frequency-based) + `ManagerResolver` |
| `src/remi/knowledge/context_builder.py` | Assembles agent context from knowledge graph + signals |
| `src/remi/knowledge/graph_retriever.py` | Retrieves entities and relationships from the graph |
| `src/remi/services/dashboard.py` | Computes director dashboard state from signals |
| `src/remi/services/manager_review.py` | Manager performance review logic |
| `src/remi/services/auto_assign.py` | Assigns unassigned properties to existing managers (never creates new ones) |
| `src/remi/shared/errors.py` | Shared error types — use these, don't invent new ones |

## Ingestion Pipeline

Ingestion is **schema-driven**. Each AppFolio report type has a `ReportSchema` in
`knowledge/ingestion/schema.py`. Adding a new report type = adding a schema definition,
not a handler file.

**Two categories:**
- **Migration** (Property Directory): creates managers + properties. Uses frequency-based
  classification to separate real manager names from operational tags (e.g. "Section 8").
  Only report type that creates `PropertyManager` / `Portfolio` records.
- **Recurring** (Delinquency, Rent Roll, Lease Expiration): creates/updates units, tenants,
  leases. Never creates managers — consumes existing property-to-portfolio mappings.

`AutoAssignService` assigns unassigned properties to *existing* managers only — it will
never create a new manager from a KB tag.

## Module Map

```
src/remi/
  agent/        AgentNode, loop, intent classifier, LLM bridge, tool executor
  agents/       YAML configs — director, researcher, action_planner, report_classifier, knowledge_enricher
  api/          FastAPI routers (17 route groups + WebSocket chat/events), schemas, middleware
  cli/          Typer CLI entry points
  config/       Settings, DI container, domain.yaml
  db/           Database engine and tables (Postgres)
  documents/    AppFolio report schema and parsers
  knowledge/    Context builder, graph retriever, entailment engine, ingestion pipeline, ontology
    ingestion/
      schema.py    ReportSchema definitions + unified ingest_report() loop
      managers.py  Frequency-based manager classification + ManagerResolver
      service.py   IngestionService — report type detection + schema dispatch
      generic.py   Fallback for unrecognized report types
      helpers.py   Address parsing, occupancy mapping
    ontology/
      bridge.py    BridgedKnowledgeGraph + build_knowledge_graph factory
      schema.py    REMI domain schema (core types, link types) + seed_knowledge_graph
      remote.py    RemoteKnowledgeGraph (HTTP client for sandbox)
  llm/          LLM provider ports + adapters (Anthropic, OpenAI, Gemini)
  models/       Pydantic models (properties, signals, ontology, chat, documents, trace, memory, sandbox, tools)
  observability/ Structured logging (structlog), events, tracer
  sandbox/      Isolated code execution (local subprocess sandbox, data bridge)
  services/     Domain services (dashboard, manager review, document ingestion, lease/portfolio/property/maintenance queries, rent roll, snapshots, auto-assign)
  shared/       Enums, errors, ids, clock, result, paths, text — cross-cutting primitives only
  stores/       Storage adapters (properties, signals, documents, vectors, chat, trace, memory, snapshots, Postgres variants)
  tools/        Agent tool implementations (ontology, documents, memory, sandbox, trace, vectors, actions, workflows)
  vectors/      Embedding pipeline, embedder
```

## When Making Structural Decisions

- Before creating a new file, say where it goes and why
- Before adding logic to an existing file, flag if it's growing beyond a single responsibility
- Prefer small focused modules — don't accumulate logic in existing files
- `shared/` is for primitives only — no business logic there
- `services/` is for domain logic that isn't part of the agent loop
