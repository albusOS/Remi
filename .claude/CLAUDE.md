# REMI

AI agent operating system for property management directors.
The director's core question: **which of my managers needs my attention, and why?**

## Commands

```bash
uv run pytest tests/ -q              # run all tests
uv run remi serve --seed             # start API server with demo data
uv run remi onto signals             # show active signal definitions
uv run remi trace list               # recent traces
```

## Tooling

- Always use `uv run` to execute Python — never `python` directly
- Always use `uv add` to add dependencies — never `pip install`
- Never reference `.venv/` paths

## Error Handling — Zero Silent Swallows

Every exception must either **propagate** or be **logged at warning+ with
`exc_info=True`**. No other option.

- **Banned:** `except Exception: pass`, bare `except:`, swallowed returns without logging
- **Required:** `structlog` for all logging — not `print` or `logging`

## Type Safety — No `Any`, No Untyped `dict`

- `dict[str, Any]` as return/parameter → use a Pydantic model or TypedDict
- `-> Any` → be explicit
- Narrow existing `Any`/`dict` types when touching old code

## Structural Design Principles

### Screaming Architecture
Folders are named for what the system **does**, not what technical role
they play. `ingestion/` not `controllers/`. `signals/` not `helpers/`.

### Vertical Slicing
Group code by **business capability**. Everything related to a feature
lives together: `api/portfolio/`, `cli/intelligence/`, `services/ingestion/`.

### Clean Architecture Boundaries
Four packages with strict dependency rings:

```
types/ ← agent/ ← application/ ← shell/
```

Inner rings never import from outer rings. If they need something,
define a protocol in the inner ring, implement it in the outer.

### When Creating New Files

1. State the intended package before placing the file.
2. Name it for what it does — `bridge.py` not `knowledge_graph_adapter.py`.
3. One clear responsibility per module (~300 line soft limit).
4. New folders need a reason — don't create a folder for one file.
5. Principle of Least Astonishment — if the path would surprise a
   new developer, it's wrong.

## Architecture

```
src/remi/
  agent/           # AI OS kernel — LLM, vectors, sandbox, tracing,
                   # signals (types, TBox, stores, producers),
                   # graph, documents, DB, runtime (incl. conversation),
                   # pipeline, sessions, context, tools, workspace
  application/     # RE product (hexagonal)
                   # core/ — models, protocols, rules, events
                   # services/ — ingestion, embedding, queries, seeding, search
                   # infra/ — stores (mem, pg), ontology, ports
                   # tools/ — agent tool registrations
                   # api/ — portfolio/ operations/ intelligence/ system/
                   # cli/ — portfolio/ operations/ intelligence/ system/
  types/           # Shared vocabulary — ids, clock, errors, enums
  shell/           # Composition root — DI container, settings, API, CLI
```

**The agent reasons over data via tools** — there is no precomputed
signal engine. The TBox (`domain.yaml`) defines the vocabulary;
the agent queries the PropertyStore on demand and applies
`core/rules.py` classification helpers.

## Key Files

| File | Role |
|------|------|
| `shell/config/domain.yaml` | Source of truth for signal definitions, thresholds, rules |
| `shell/config/container.py` | DI container — pure wiring, no business logic |
| `application/agents/director/app.yaml` | Director agent manifest |
| `application/services/ingestion/service.py` | IngestionService — report type detection + dispatch |
| `application/services/ingestion/rules.py` | Deterministic column-header ingestion |
| `agent/context/builder.py` | Assembles agent context from graph + signals |
| `agent/runtime/node.py` | AgentNode — config-driven think-act-observe loop |
| `application/core/protocols.py` | Narrow per-entity repository protocols |
| `application/core/events.py` | ChangeSet — event-sourced temporal model |

## Import Rules

- Import from the **package barrel** (`__init__.py`), not from internal modules
- Every barrel must define `__all__`
- Three-segment depth max for cross-layer imports
- Never use `typing.TYPE_CHECKING` — fix the design, not the import

## What Was Deleted (Do Not Recreate)

- **Entailment engine** (`services/detection/signals/`) — agent queries data directly now
- **Snapshot/rollup system** (`SnapshotService`, `RollupStore`) — replaced by events
- **Synthetic data generation** (`seeding/synthetic.py`, `_backfill_history`)
- **Dev cache** (`StoreBundle`, `dump_state`/`load_state`)
- **Timeline recorder** (`TimelineRecorder`, `KnowledgeGraphTimelineRecorder`)

## Tests

- Only test meaningful behavior, not implementation details
- Cover real failure modes and edge cases
- Ask before writing tests if the value isn't obvious
