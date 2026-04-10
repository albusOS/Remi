---
name: platform-orientation
description: Start, run, and navigate the REMI codebase. Use when setting up the platform for the first time, running the server or CLI, understanding where code lives, or getting a ground-truth picture of what's wired vs dead code.
---

# REMI Platform Orientation

## Starting the platform

```bash
# 1. Copy and fill env vars
cp .env.example .env
# Set ANTHROPIC_API_KEY at minimum

# 2. Start the API server
uv run remi serve

# 3. Verify health
curl http://localhost:8000/health
```

The default config (`config/base.yaml`) uses in-memory storage — no database required.
Everything resets on server restart. That is intentional for dev.

For persistent storage, set `DATABASE_URL` and `REMI_CONFIG_ENV=dev`:
```bash
REMI_CONFIG_ENV=dev uv run remi serve
```

## CLI commands

```bash
# Portfolio
uv run remi portfolio managers
uv run remi portfolio properties
uv run remi portfolio rent-roll <property-id>
uv run remi portfolio manager-review <manager-id>
uv run remi portfolio rankings

# Operations
uv run remi operations leases
uv run remi operations maintenance
uv run remi operations delinquency
uv run remi operations expiring-leases --days 90

# Intelligence
uv run remi intelligence dashboard
uv run remi intelligence search "query text"
uv run remi intelligence vacancies

# Ingestion
uv run remi ingestion upload <path-to-file>
uv run remi ingestion documents
uv run remi ingestion document-search "query"
```

All CLI commands return JSON by default. When `REMI_API_URL` is set, they
proxy to the running API instead of booting a local container.

## Sample data

```
data/sample_reports/Alex_Budavich_Reports/
```

Upload order matters — property directory first (seeds manager/property source of truth):
```bash
uv run remi ingestion upload "data/sample_reports/Alex_Budavich_Reports/property_directory-20260330.xlsx"
uv run remi ingestion upload "data/sample_reports/Alex_Budavich_Reports/Rent Roll_Vacancy (1).xlsx"
uv run remi ingestion upload "data/sample_reports/Alex_Budavich_Reports/Delinquency.xlsx"
```

## HTTP API endpoints

Base URL: `http://localhost:8000/api/v1`

```
GET  /health
POST /api/v1/agents/{name}/ask         # agent chat (NDJSON stream)
GET  /api/v1/portfolio/managers
GET  /api/v1/portfolio/properties
GET  /api/v1/operations/leases
GET  /api/v1/operations/maintenance
GET  /api/v1/intelligence/dashboard
GET  /api/v1/intelligence/search?q=...
POST /api/v1/ingestion/upload          # multipart file upload
GET  /api/v1/ingestion/documents
GET  /api/v1/feed?after={cursor}       # domain event polling
WS   /api/v1/feed/ws                   # domain event push
```

## Agents

| Name | Kind | Placement | What it does |
|---|---|---|---|
| `director` | Agent | inline | Primary chat agent — user-facing orchestrator |
| `researcher` | Agent | worker | Statistical analysis with bash/python/pandas |
| `ingester` | Workflow | worker | Document ingestion DAG |
| `brief_writer` | Pipeline | inline | Manager meeting brief |

Call an agent:
```bash
curl -N -X POST http://localhost:8000/api/v1/agents/director/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "show me the portfolio dashboard"}'
```
The response is NDJSON — one event per line: `delta`, `tool_call`, `tool_result`, `done`.

## Key file index (code-verified)

### Composition root
```
src/remi/shell/config/container.py      # DI wiring — what's actually registered
src/remi/shell/config/settings.py       # All settings + env var loading
src/remi/shell/config/capabilities.py   # Manifest discovery + API/CLI wiring
src/remi/shell/config/domain.yaml       # Entity types, relationships, processes
src/remi/shell/api/main.py              # FastAPI app factory
src/remi/shell/cli/main.py              # Typer CLI entrypoint
src/remi/shell/cli/client.py            # HTTP proxy client (used by sandbox)
```

### Agent kernel
```
src/remi/agent/serve/kernel.py          # Kernel.boot() — all infrastructure wired here
src/remi/agent/runtime/runner.py        # AgentRuntime — ask() entry point
src/remi/agent/runtime/node.py          # AgentNode — YAML config → execution
src/remi/agent/runtime/loop.py          # Think-act-observe loop (tool budget, scratchpad)
src/remi/agent/workflow/engine.py       # WorkflowRunner — DAG scheduler
src/remi/agent/tasks/supervisor.py      # TaskSupervisor — delegation entry point
src/remi/agent/events/bus.py            # EventBus — domain event pub-sub
```

### Product tools (what the LLM actually calls)
```
src/remi/application/tools/query.py         # unified query tool — all 20 read ops
src/remi/application/tools/aggregators.py   # pure group-by transforms (no I/O)
src/remi/application/tools/detail.py        # EntityDetailHandler — 360° entity views
src/remi/application/tools/documents.py     # document_list, document_query, document_search
src/remi/application/tools/mutations.py     # assert_fact, add_context
src/remi/application/ingestion/tools.py     # 6 ingest_* tools for the ingester workflow
```

### Domain (current paths — undergoing migration to capability slices)
```
src/remi/application/core/protocols.py      # PropertyStore — single storage port
src/remi/application/core/models/           # All Pydantic domain models
src/remi/application/portfolio/managers.py  # ManagerResolver        → manager-review/
src/remi/application/portfolio/dashboard.py # DashboardBuilder       → portfolio-health/
src/remi/application/operations/delinquency.py  # DelinquencyResolver → delinquency-review/
src/remi/application/intelligence/trends.py     # TrendResolver       → entity-search/
src/remi/application/ingestion/vocab.py     # column vocabulary + report profiles → document-ingestion/
src/remi/application/ingestion/rules.py     # junk filtering, address normalization → document-ingestion/
```

The `portfolio/`, `operations/`, and `intelligence/` directories are transitional.
New code goes in `src/remi/application/<capability-name>/`. See `skill-capability-architecture` rule.

### Agent manifests (target: migrate to `scripts/app.yaml` inside capability slices)
```
src/remi/application/agents/director/app.yaml       → director-copilot/scripts/app.yaml
src/remi/application/agents/researcher/app.yaml     → deep-research/scripts/app.yaml
src/remi/application/agents/ingester/app.yaml       → document-ingestion/scripts/app.yaml
src/remi/application/agents/brief_writer/app.yaml   → manager-meeting-prep/scripts/app.yaml
```

## Dead code — delete these files

Three tool provider classes exist but are **never instantiated or registered**.
Delete them outright — do not reference or modify them:

- `src/remi/application/portfolio/tools.py` → `PortfolioToolProvider`
- `src/remi/application/operations/tools.py` → `OperationsToolProvider`
- `src/remi/application/intelligence/tools.py` → `IntelligenceToolProvider`

These are a prior iteration of the tool architecture (per-slice tools) superseded
by the unified `QueryToolProvider`. The migration is complete; the old files were not deleted.

## What's actually wired (container.py trace)

```
Kernel.boot() registers on ALL tool registries:
  bash, python          ← AnalysisToolProvider
  memory_write/read     ← MemoryToolProvider
  delegate_to_agent     ← DelegationToolProvider
  ask_human             ← HumanToolProvider (declared in no agent's YAML yet)

Container.__init__() adds product tools:
  query                 ← QueryToolProvider        (20 operations)
  document_list,
  document_query,
  document_search       ← DocumentToolProvider
  assert_fact,
  add_context           ← MutationToolProvider
  ingest_*              ← IngestionToolProvider    (6 tools, ingester workflow only)
```

The director's YAML `tools:` list selects which registered tools it can call.
It lists: `query, document_list, document_query, assert_fact, add_context,
delegate_to_agent, memory_write, memory_read`.
No bash/python — computation is delegated to researcher.

## Config files

```
config/base.yaml      # always loaded first (in-memory, port 8000)
config/dev.yaml       # REMI_CONFIG_ENV=dev — postgres, debug logging
config/local.yaml     # personal overrides, gitignored
config/prod.yaml      # production
```

YAML values can reference env vars: `dsn: ${DATABASE_URL}`.

## Running tests

```bash
uv run pytest                          # full suite
uv run pytest tests/ingestion/         # ingestion only
uv run pytest tests/unified/           # ring + circular import checks
uv run ruff check src/                 # lint
uv run mypy src/                       # type check
```
