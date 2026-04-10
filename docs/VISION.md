# REMI: Agent OS → SDK → Products

This document captures the full vision, technical requirements, and concrete
migration plan for evolving REMI from a single-process monolith into a
standalone Agent OS that products (including the real estate solution) are
built on.

Written: April 2026. This is the north star. Every coding session references
this. If a change contradicts this document, the change is wrong.

---

## 1. What REMI Is

REMI is an **Agent OS** — a runtime that boots, schedules, isolates, and
observes AI agents. It is not a framework you import. It is a system you
deploy.

The primary interface is **YAML manifests** + **CLI commands**, not Python
constructors. You declare agents, tools, delegation edges, and resource
budgets in YAML. The OS runs them.

```
YAML manifests → remi agent serve → running agents with enforced boundaries
```

**Python SDK** is for extension — writing custom tool providers, store
adapters, event subscribers. It is the secondary interface.

### The OS Metaphor (Taken Seriously)

| OS Concept | REMI Equivalent |
|---|---|
| Process | Agent run (own sandbox, own budget, own lifecycle) |
| Scheduler | TaskSupervisor + TaskPool (priority, fairness, backpressure) |
| Resource limits | RuntimeConfig.resources (tokens, rounds, timeout, memory — enforced) |
| IPC / signals | EventBus (pub/sub, cross-process via Redis) |
| Process lifecycle | Task state machine (pending → running → done/failed/cancelled) |
| File system | Shared stores (Postgres), agent memory (namespaced) |
| Supervisor (systemd) | TaskSupervisor (restart, kill, observe from outside) |

**If a manifest field isn't enforced by the runtime, it's a bug.**
Don't declare what you can't enforce.

---

## 2. The Product Model

Each agent is a **standalone product surface**, not a subroutine hidden
behind delegation. Like ChatGPT lets users choose between GPT-4o and o1,
products built on REMI let users choose which agent to interact with.

```
┌──────────────────────────────────────┐
│  [⚡ Fast Mode]  [🔬 Deep Research]  │  ← user toggles
│                                      │
│  Each mode is a different agent:     │
│  - Different capabilities            │
│  - Different latency expectations    │
│  - Different cost                    │
│  - Own chat sessions and memory      │
└──────────────────────────────────────┘
```

Agents can also delegate to each other (coordinator → specialist), and
background agents can run without direct user interaction (ingestion,
scheduled analysis). But the fundamental unit is: **one agent = one
independently addressable service**.

---

## 3. Deployment Model

The same YAML manifest runs in three topologies. No code changes between them.

### `placement: inline`

Agent runs as a coroutine in the caller's process. Same event loop.
Used for: user-facing chat agents that need streaming, lightweight agents,
development mode.

### `placement: worker`

Agent runs in a separate worker process that pulls from a shared task queue
(Redis). Used for: background agents (ingestion, scheduled research), heavy
computation, fault isolation.

### `placement: service`

Agent runs as its own long-lived process with its own HTTP endpoint. Boots
independently. Used for: agents that need dedicated resources, independent
scaling, hard isolation, or direct user interaction from a different entry
point.

### Topology examples

**Development (single process):**
```bash
remi serve --all-inline
# Everything in one process. In-memory stores. Zero config.
```

**Staging (API + workers):**
```bash
remi serve                    # API server (director inline)
remi worker                   # Worker fleet (ingester, researcher)
```

**Production (multi-service):**
```bash
remi serve                            # API gateway + director
remi agent serve researcher --port 8001   # Deep research service
remi agent serve ingester --port 8002     # Ingestion service
# All share Postgres + Redis
```

---

## 4. Architecture Boundaries

Four packages. The directory tree enforces the dependency rules.

```
src/
  remi/
    types/       ← Pure vocabulary. Imports nothing.
    agent/       ← The OS kernel. Imports types/ only.
    application/ ← One product (real estate). Imports agent/ + types/.
    shell/       ← Composition root. Imports everything.
```

### What lives where

**`types/`** — IDs, clock, errors, enums, result types. No logic. No
dependencies. This is shared vocabulary.

**`agent/`** — The kernel. Everything needed to boot and run any agent:

```
agent/
  runtime/       Agent loop, sessions, context, compaction, retry
  tasks/         Delegation, scheduling, lifecycle, pool
  events/        Pub/sub bus, buffer, domain events
  memory/        Persistent namespaced agent memory
  llm/           Multi-provider LLM access (Anthropic, OpenAI, Gemini)
  sandbox/       Isolated code execution (local, Docker)
  vectors/       Embedding + semantic search
  documents/     Document parsing + chunked storage
  tools/         Tool registry, providers, execution
  workflow/      DAG engine (LLM, tool, gate, agent steps)
  graph/         Knowledge graph primitives
  sessions/      Chat session stores
  signals/       Domain schema (TBox)
  skills/        Skill discovery
  observe/       Tracing, logging, usage tracking
  context/       Context building, rendering
  workspace/     Working memory (scratchpad)
  db/            Database engine + tables
  config.py      Kernel settings (Pydantic models)
  workforce.py   Agent topology (delegation graph)
  serve/         HTTP server for agent endpoints (NEW)
  worker/        Task queue consumer (NEW)
```

The kernel NEVER imports from `application/` or `shell/`.

**`application/`** — The real estate product. One product built on the kernel:

```
application/
  core/          Domain models (Property, Lease, etc.), protocols, rules
  stores/        Domain store implementations (mem, pg)
  tools/         Domain tool providers (query, documents, ingestion)
  agents/        Agent YAML manifests (director, researcher, etc.)
  portfolio/     Portfolio surface (API, CLI, resolvers)
  operations/    Operations surface (API, CLI, resolvers)
  intelligence/  Intelligence surface (API, CLI, resolvers)
  ingestion/     Document ingestion pipeline
  events/        Event feed projection (HTTP poll, WebSocket)
```

**`shell/`** — Composition root. Discovers kernel + product, wires them:

```
shell/
  config/        Container, settings, capabilities, domain.yaml
  api/           FastAPI app factory, chat endpoints, middleware
  cli/           Typer CLI entry point, client, output helpers
```

### The Hard Rules

1. **`agent/` never imports `application/` or `shell/`.** CI enforces this.
2. **`application/` never imports `shell/`.** (Current CLI modules violate
   this — must be fixed.)
3. **`types/` imports nothing.**
4. **`shell/` imports everything** (it's the composition root).
5. **New kernel features require a product use case.** Don't build
   speculatively.
6. **Every protocol needs two implementations.** In-memory for dev,
   Postgres/Redis for production.
7. **Manifests are the source of truth.** If YAML declares it, the
   runtime enforces it.

---

## 5. Communication Primitives

Agents communicate through three channels. No others exist.

### Delegation (request/response)

Parent agent sends a task to a child agent, waits for the result.
Mediated by `TaskSupervisor`. Transport: in-process call (inline) or
HTTP (service) or task queue (worker).

```
Director →[delegate_to_agent]→ TaskSupervisor →[TaskPool]→ Researcher
                                                              ↓
Director ←[TaskResult]←←←←←←← TaskSupervisor ←←←←←←←←←← Researcher
```

### Events (pub/sub broadcast)

Any agent publishes domain events. Any subscriber reacts. Transport:
in-memory callbacks (dev) or Redis pub/sub (production). Events cross
process boundaries.

```
Ingester →[ingestion.complete]→ EventBus → Frontend (WebSocket)
                                         → Subscriber (spawn analysis)
```

### Shared state (stores)

Agents read/write to shared stores. Transport: in-memory dicts (dev)
or Postgres (production). No direct agent-to-agent data passing outside
of delegation and events.

### What does NOT exist

- Agent-to-agent chat (no peer conversations)
- Shared scratchpads between concurrent agents
- Message queues between specific agent pairs
- Any communication channel not listed above

---

## 6. Resource Enforcement

Every budget declared in a manifest MUST be enforced at runtime.

| Resource | Declared in | Enforced by |
|---|---|---|
| `timeout_seconds` | `runtime.resources` | `TaskPool` (asyncio.wait_for) |
| `max_tool_rounds` | `runtime.resources` | Agent loop (round counter) |
| `max_tokens` | `runtime.resources` | Agent loop (cumulative token tracking) |
| `max_memory_mb` | `runtime.resources` | Container/cgroup (service mode) or logged warning |
| `max_concurrency` | `runtime.scaling` | `TaskPool` (semaphore per agent type) |
| `queue_priority` | `runtime.scaling` | `TaskPool` (priority lanes) |

If enforcement is not implemented for a field, the field must not appear
in the manifest spec. No aspirational declarations.

---

## 7. State Management

### What MUST be in Postgres (production)

- Domain entities (properties, leases, units, etc.) — product-specific
- Agent memory (namespaced, importance-ranked)
- Chat sessions (multi-turn state)
- Documents + content (parsed chunks, rows)
- Vector embeddings
- Task history (completed tasks, for observability)
- Event log (for replay and debugging)

### What MUST be in Redis (production)

- Event bus (pub/sub — real-time delivery across processes)
- Task queue (job dispatch — worker pulls from queue)
- Ephemeral state (rate limiting, locks, cache)

### What stays in-memory (dev mode only)

Everything above has an in-memory implementation for zero-config
development. `remi serve --all-inline` uses only in-memory backends.
This is the default. Production settings switch to Postgres + Redis.

---

## 8. The Real Estate Product as Reference Implementation

The RE product (`application/`) is the **first product built on the
kernel**. It exercises every kernel primitive. It is the proof that the
SDK works.

### How it uses the kernel

| Kernel Primitive | RE Product Usage |
|---|---|
| Agent runtime | Director (copilot), Researcher (deep analysis) |
| Delegation | Director → Researcher, Ingester, Brief Writer |
| Events | Ingestion lifecycle, frontend real-time updates |
| Memory | Cross-session learning, meeting brief recall |
| Sandbox | Python/bash for computation (researcher) |
| Documents | AppFolio report ingestion and storage |
| Vectors | Semantic search over entities |
| Workflow engine | (Future: structured ingestion pipelines) |
| Sessions | Multi-turn chat with director and researcher |
| Tools | query (12 operations), document_list, document_query, ingest_* |

### The discipline

Every time the RE product needs a kernel feature:
1. **Would a coding agent product also need this?** → Build it in `agent/`
2. **Is this specific to property management?** → Build it in `application/`
3. **Does the RE product expose a gap in the kernel?** → Document the gap,
   build the generic solution in `agent/`, use it from `application/`

The RE product tells us WHAT to build. It does not tell us HOW to build it.

### RE agent topology

```
User-facing (chat: true, audience: user):
  director     — fast copilot, inline, streams to user
  researcher   — deep analysis, worker/service, expensive

System (chat: false, audience: system/internal):
  ingester     — document extraction, worker, triggered by uploads
  brief_writer — meeting briefs, inline, triggered by API
```

Users choose between director (fast) and researcher (deep) like choosing
between GPT-4o and o1. Ingester and brief_writer are system agents
triggered programmatically.

---

## 9. SDK Developer Experience

For someone building a new product on the kernel:

### Minimal agent (hello world)

```yaml
# agents/greeter/app.yaml
apiVersion: remi/v1
kind: Agent
metadata:
  name: greeter
  description: A friendly greeter
  audience: user
  chat: true
runtime:
  placement: inline
  resources:
    timeout_seconds: 30
    max_tool_rounds: 3
modules:
  - id: greeter
    kind: agent
    config:
      provider: anthropic
      model: claude-haiku-4-5-20251001
      system_prompt: "You are a friendly greeter. Say hello."
      tools: []
```

```bash
export ANTHROPIC_API_KEY=sk-...
remi agent serve greeter --port 8000
# POST http://localhost:8000/api/v1/agents/greeter/ask
# {"question": "Hi!"}
```

### Custom tool

```python
# tools/weather.py
from remi.agent import ToolProvider, ToolRegistry, ToolDefinition, ToolArg

class WeatherToolProvider(ToolProvider):
    def register(self, registry: ToolRegistry) -> None:
        async def get_weather(args: dict) -> dict:
            city = args["city"]
            return {"city": city, "temp": 72, "condition": "sunny"}

        registry.register("get_weather", get_weather, ToolDefinition(
            name="get_weather",
            description="Get current weather for a city",
            args=[ToolArg(name="city", description="City name", required=True)],
        ))
```

### Multi-agent team

```yaml
# agents/coordinator/app.yaml
delegates_to:
  - agent: analyst
    description: "Deep data analysis"
    constraints:
      timeout_seconds: 120

# agents/analyst/app.yaml
runtime:
  placement: worker
```

```bash
remi serve              # coordinator inline
remi worker             # analyst runs on worker
```

---

## 10. Concrete Migration Plan

### What the file tree looks like AFTER migration

```
src/remi/
  types/                    ← unchanged
  agent/                    ← kernel (gains serve/ and worker/)
    ...existing modules...
    serve/                  ← NEW: HTTP server for agent endpoints
      __init__.py
      app.py                  FastAPI app (agent CRUD, ask, sessions)
      lifespan.py             Boot/shutdown lifecycle
    worker/                 ← NEW: task queue consumer
      __init__.py
      consumer.py             Redis queue polling loop
      cli.py                  `remi worker` command
    cli/                    ← NEW: kernel CLI commands
      __init__.py
      main.py                 `remi agent serve`, `remi agent run`
  application/              ← RE product (unchanged structure)
  shell/                    ← RE composition root (slimmed)
```

### Phase 1: Make the Kernel Bootable (no product code needed)

**Goal:** `remi agent serve <name> --port 8000` works with just a YAML
manifest and optional tool providers. No `application/` or `shell/`
required.

**Create:**

| Path | What |
|---|---|
| `agent/serve/__init__.py` | Barrel |
| `agent/serve/app.py` | Generic FastAPI app: `/agents/{name}/ask`, `/agents/{name}/sessions/*`, `/health` |
| `agent/serve/lifespan.py` | Boots kernel from settings: providers, sandbox, memory, sessions, events, tools |
| `agent/serve/boot.py` | `Runtime.boot(settings) → AgentRuntime` — the one-call bootstrap |
| `agent/worker/__init__.py` | Barrel |
| `agent/worker/consumer.py` | Redis task queue consumer loop |
| `agent/cli/__init__.py` | Barrel |
| `agent/cli/main.py` | `remi agent serve <name>`, `remi agent run <name> <question>`, `remi agent ps` |

**Modify:**

| Path | Change |
|---|---|
| `agent/runtime/runner.py` | `DomainTBox` becomes optional (default to empty) |
| `agent/runtime/runner.py` | `ask()` accepts `manifest_path=` to bypass global registry |
| `agent/workflow/registry.py` | Add `register_manifests_from_directory(path)` |
| `agent/runtime/loop.py` | Enforce `max_tool_rounds` from RuntimeConfig |
| `agent/runtime/node.py` | Enforce `max_tokens` (cumulative tracking + cutoff) |
| `agent/tasks/factory.py` | Implement `RedisTaskPool` (or stub with clear interface) |
| `agent/events/factory.py` | Implement `RedisEventBus` (or stub with clear interface) |
| `agent/sessions/factory.py` | Add `postgres` backend for ChatSessionStore |
| `agent/config.py` | Add `serve` settings (host, port, agent_name) |

**Delete nothing in Phase 1.** The existing product keeps working.

### Phase 2: Redis Backends (Cross-Process Communication)

**Goal:** Agents in different processes can delegate, publish events,
and share sessions.

**Create:**

| Path | What |
|---|---|
| `agent/tasks/adapters/redis_pool.py` | `RedisTaskPool` — enqueue tasks, workers dequeue |
| `agent/events/adapters/__init__.py` | Barrel |
| `agent/events/adapters/redis_bus.py` | `RedisEventBus` — Redis pub/sub |
| `agent/events/adapters/redis_buffer.py` | `RedisEventBuffer` — Redis Streams |
| `agent/sessions/adapters/__init__.py` | Barrel |
| `agent/sessions/adapters/pg.py` | `PostgresChatSessionStore` |

**Modify:**

| Path | Change |
|---|---|
| `agent/tasks/factory.py` | Wire `redis` backend to `RedisTaskPool` |
| `agent/events/factory.py` | Wire `redis` backend to `RedisEventBus` |
| `agent/sessions/factory.py` | Wire `postgres` backend to `PostgresChatSessionStore` |
| `agent/tasks/supervisor.py` | Route by placement: inline → local executor, worker → queue, service → remote HTTP |

### Phase 3: Product Decoupling

**Goal:** `application/` is a plugin that registers into the kernel,
not a peer that the shell hardcodes.

**Modify:**

| Path | Change |
|---|---|
| `shell/config/container.py` | Extract kernel wiring into `agent/serve/boot.py`; container calls `Runtime.boot()` then registers product tools/stores |
| `shell/config/capabilities.py` | Keep for RE product; kernel has its own manifest discovery |
| `application/*/cli.py` | Remove imports of `shell.config.container` — use a product-level boot function or the kernel's serve layer |

**Move:**

| From | To | Why |
|---|---|---|
| `shell/api/chat.py` | `agent/serve/app.py` | Chat endpoints are kernel, not product |
| `shell/api/dependencies.py` | Split: kernel deps → `agent/serve/`, product deps stay in `shell/` | |

**The RE product's API routes, CLI commands, tools, and stores stay in
`application/`.** They register into the kernel at boot time via
the container.

### Phase 4: Multi-Service Deployment

**Goal:** Each agent can run as its own service. The RE product deploys
as director (inline) + researcher (service) + ingester (worker).

**Create:**

| Path | What |
|---|---|
| `agent/serve/discovery.py` | Service registry: agent name → URL (config-based or Consul) |
| `docker/Dockerfile.agent` | Base image for agent services |
| `docker/docker-compose.multi.yaml` | Multi-service compose for RE product |

**Modify:**

| Path | Change |
|---|---|
| `agent/tasks/supervisor.py` | Use service registry to route `placement: service` to `RemoteAgentExecutor` |
| `agent/tasks/adapters/remote.py` | Production-harden: retries, auth, health checks |

---

## 11. What NOT to Do

Rules for every future coding session. Violations are rejected regardless
of how "practical" they seem.

1. **Never add domain-specific logic to `agent/`.** If you're writing
   "property", "lease", "manager", "rent roll" in `agent/`, you're in
   the wrong package.

2. **Never import `application/` or `shell/` from `agent/`.**

3. **Never declare a manifest field that the runtime doesn't enforce.**
   Aspirational YAML is a lie.

4. **Never bypass TaskSupervisor for agent execution.** All agent work
   goes through the supervisor. Direct `AgentRuntime.ask()` calls from
   product code are banned — submit a `TaskSpec`.

5. **Never hardcode topology in Python.** If you're writing
   `asyncio.create_task()` in product code, you're bypassing the pool.

6. **Never build kernel features speculatively.** A concrete product
   use case must exist.

7. **Never create in-memory-only implementations without a protocol.**
   Every store, bus, pool, and session backend must have an ABC. The
   in-memory impl is for dev; the protocol is for production.

8. **Never let `application/` import from `shell/`.** This is currently
   violated by CLI modules. Fix it; don't add to it.

9. **Never create peer-to-peer agent communication.** Agents communicate
   through delegation (via supervisor), events (via bus), or shared
   state (via stores). No other channels.

10. **Never merge code that introduces a new `Any` return type, a bare
    `except:`, a `print()` statement, or a silent exception swallow.**

---

## 12. Success Criteria

The kernel is done when:

1. `remi agent serve greeter --port 8000` boots a minimal agent with
   zero product code and serves chat over HTTP.

2. `remi worker` polls a Redis task queue and executes delegated agent
   tasks in a separate process.

3. The RE product's director can delegate to a researcher running in a
   different process, and the result comes back correctly.

4. An event published by the ingester (in a worker process) is received
   by the API server's WebSocket connections (in the main process)
   via Redis pub/sub.

5. All manifest fields under `runtime.resources` are enforced. Exceeding
   `max_tool_rounds` stops the loop. Exceeding `max_tokens` stops the
   loop. Exceeding `timeout_seconds` cancels the task.

6. Someone unfamiliar with the RE product can create a new agent
   product using only `agent/` + `types/` and the YAML manifest spec.
