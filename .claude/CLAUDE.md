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

**Acceptable patterns:**
- `except ImportError` for optional-dependency guards (must raise or feature-flag)
- `except (KeyboardInterrupt, EOFError)` in CLI interactive loops
- `except Exception` that logs at `warning`/`error` with `exc_info=True` **and** surfaces the failure to the caller

**Batch/pipeline catch-and-continue** must:
1. Log at `warning` with `exc_info=True`
2. Record the failure in a result object the caller can inspect

Use `structlog` for all logging, not `print` or `logging` directly.

## Type Safety — No `Any`, No Untyped `dict`

**Banned in new code:**
- `dict[str, Any]` as a function return or parameter — use a Pydantic model or TypedDict
- `-> Any` return annotations — be explicit
- `list[dict]` — model the items

**When touching existing `Any`/`dict` code**, narrow the type if feasible.

## Tests

- Only write tests for meaningful behavior — not implementation details
- Tests should cover real failure modes and edge cases
- Ask before writing tests if the value isn't obvious

## Architecture: Two Halves + Shell

Full rationale: `docs/architecture.md`

The generic/RE boundary is visible in `ls`. Everything above `portfolio/`
is domain-agnostic. Everything from `portfolio/` through `configs/` is
real estate. `shell/` is the composition root.

```
src/remi/

  # ── Domain-agnostic capabilities ───────────────────────────
  types/       Pure vocabulary — ids, clock, errors, enums, result, text
  db/          Database engine + table metadata
  llm/         LLM provider ports + adapters
  vectors/     Embedding ports + adapters, pipeline
  sandbox/     Code execution ports + adapters
  observe/     Structured logging, tracing
  signals/     Signal types, stores, engine, composite
  graph/       Knowledge graph types, bridge, retriever
  documents/   Document types, stores, parsers
  agent/       LLM runtime, context builder, perception, conversation

  # ── Real estate (the product) ──────────────────────────────
  portfolio/   Entity DTOs + protocols + business rules
  stores/      RE persistence adapters (mem, pg, rollups)
  queries/     RE query services (dashboard, rent roll, etc.)
  evaluators/  RE signal producers (delinquency, lease, etc.)
  ingestion/   RE inbound data pipeline
  ontology/    RE knowledge graph schema
  search/      RE-aware hybrid search + patterns
  tools/       RE agent capabilities
  configs/     RE agent YAML manifests

  # ── Composition root ───────────────────────────────────────
  shell/       DI container, settings, domain.yaml, API, CLI
```

**When creating or moving code, say which package it belongs to before placing it.**

Key constraint: the LLM agent does NOT detect signals — the entailment engine does.
The LLM's job is abductive reasoning: explain, connect, recommend, codify.

## Key Files

| File | Role |
|------|------|
| `src/remi/shell/config/domain.yaml` | Source of truth for signal definitions, thresholds, rules |
| `src/remi/shell/config/container.py` | DI container — wires everything |
| `src/remi/configs/director/app.yaml` | Director agent manifest |
| `src/remi/configs/researcher/app.yaml` | Researcher agent manifest |
| `src/remi/agent/node.py` | AgentNode — config-driven think-act-observe loop |
| `src/remi/signals/engine.py` | Entailment engine — evaluates rules, produces signals |
| `src/remi/ingestion/service.py` | IngestionService — report type detection + dispatch |
| `src/remi/ingestion/managers.py` | Manager classification + ManagerResolver |
| `src/remi/agent/context_builder.py` | Assembles agent context from graph + signals |
| `src/remi/graph/retriever.py` | Retrieves entities and relationships from the graph |
| `src/remi/queries/dashboard.py` | Computes director dashboard state from signals |
| `src/remi/queries/managers.py` | Manager performance review logic |
| `src/remi/queries/auto_assign.py` | Assigns unassigned properties to existing managers |
| `src/remi/types/errors.py` | Shared error types |

## Ingestion Pipeline

Ingestion is **schema-driven**. Adding a new report type = adding a schema
definition, not a handler file.

**Two categories:**
- **Migration** (Property Directory): creates managers + properties. Uses frequency-based
  classification to separate real manager names from operational tags.
- **Recurring** (Delinquency, Rent Roll, Lease Expiration): creates/updates units, tenants,
  leases. Never creates managers — consumes existing property-to-portfolio mappings.

## When Making Structural Decisions

- Before creating a new file, say which package it goes in and why
- Before adding logic to an existing file, flag if it's growing beyond a single responsibility
- Prefer small focused modules
- `types/` is for primitives only — no business logic there
- `queries/` is for domain query logic that isn't part of the agent loop
