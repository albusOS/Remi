---
name: add-agent
description: Create a new agent, pipeline, or workflow in REMI. Use when you need a new specialist agent, a new multi-step pipeline, or a new DAG workflow. Covers manifest creation, capability wiring, tool access, and delegation.
---

# Adding an Agent, Pipeline, or Workflow

## Three manifest kinds

| `kind` | Execution model | When to use |
|---|---|---|
| `Agent` | Full think-act-observe loop with LLM + tools | Specialist that needs to reason and decide |
| `Workflow` | Explicit DAG with `depends_on` and gates | Multi-step process with conditional branches |
| `Pipeline` | Sequential steps, implicit dependencies | Linear: fetch data → transform → format |

## Step 1 — Create the manifest file

```
src/remi/application/agents/<name>/app.yaml
```

The directory name is just for organization. The canonical name comes from
`metadata.name` in the YAML — that's what the system uses everywhere.

Auto-discovery scans all `application/**/app.yaml` files at startup.
No Python registration needed for agents that have no API routes or CLI.

## Step 2 — Write the manifest

### Minimal Agent manifest

```yaml
apiVersion: remi/v1
kind: Agent

metadata:
  name: my_agent
  version: "1.0.0"
  description: >
    One sentence: what this agent does and when to use it.
  tags: [your, tags]
  domain: real-estate
  audience: internal   # or user
  chat: false          # true if this can be called directly via /agents/ask

runtime:
  placement: worker    # worker (background) or inline (streaming chat)
  isolation: sandbox   # sandbox (has bash/python) or none
  durability: ephemeral
  resources:
    timeout_seconds: 120
    max_tool_rounds: 10
    max_tokens: 50000
  scaling:
    max_concurrency: 2
    queue_priority: normal

modules:
  - id: my_agent
    kind: agent
    description: >
      What this agent module does.
    config:
      provider: anthropic
      model: claude-haiku-4-5-20251001   # haiku for cheap tasks, sonnet for complex
      temperature: 0.2
      max_tokens: 4096
      max_iterations: 12

      system_prompt: |
        You are ...

        ## Your job
        ...

      input_template: "{input}"
      output_contract: conversation
      response_format: text

      tools:
        - name: query
        - name: bash      # only if isolation: sandbox
        - name: python    # only if isolation: sandbox
        - name: delegate_to_agent
        - name: memory_write
        - name: memory_read
```

### Minimal Pipeline manifest (sequential, no LLM branches)

```yaml
apiVersion: remi/v1
kind: Pipeline

metadata:
  name: my_pipeline
  version: "1.0.0"
  description: >
    What this pipeline does.
  tags: []
  domain: real-estate
  audience: internal
  chat: false

runtime:
  placement: inline
  isolation: none
  durability: ephemeral
  resources:
    timeout_seconds: 60
    max_tokens: 20000
  scaling:
    max_concurrency: 4
    queue_priority: normal

defaults:
  provider: anthropic
  model: claude-haiku-4-5-20251001

context_mode: accumulate   # each step's dict output merges into shared context

steps:
  - id: fetch
    kind: transform
    tool: query             # in-process, no LLM

  - id: format
    kind: llm
    temperature: 0.3
    max_tokens: 2048
    response_format: json
    system_prompt: |
      ...
    input_template: >
      Data: {steps.fetch}
```

### Minimal Workflow manifest (DAG with gates)

```yaml
apiVersion: remi/v1
kind: Workflow

metadata:
  name: my_workflow
  version: "1.0.0"
  description: >
    What this workflow does.
  tags: []
  domain: real-estate
  audience: internal
  chat: false

runtime:
  placement: worker
  isolation: none
  durability: ephemeral
  resources:
    timeout_seconds: 180
    max_tokens: 30000
  scaling:
    max_concurrency: 2
    queue_priority: normal

defaults:
  provider: anthropic
  model: claude-haiku-4-5-20251001

context_mode: accumulate

steps:
  - id: step_a
    kind: transform
    tool: some_tool

  - id: gate
    kind: gate
    condition: not context.some_flag
    depends_on: [step_a]

  - id: step_b
    kind: llm_tools
    depends_on: [gate]
    tools: some_tool
    system_prompt: |
      ...
    input_template: "{steps.step_a}"
    response_format: json

  - id: step_c
    kind: transform
    tool: another_tool
    depends_on: [step_a]

wires:
  # Optional wire: step_c gets step_b's output when it ran, but doesn't gate on it
  - {source: step_b.result, target: step_c.extra_input, optional: true}
```

## Step 3 — Tool access rules

Tools available to an agent depend on two things:
1. What's registered in the tool registry (by kernel + container)
2. What the agent declares in its `tools:` YAML list

**Always registered (any agent can declare these):**
```yaml
- name: query              # all 20 read operations
- name: document_list
- name: document_query
- name: document_search
- name: assert_fact
- name: add_context
- name: delegate_to_agent
- name: memory_write
- name: memory_read
- name: bash               # only useful with isolation: sandbox
- name: python             # only useful with isolation: sandbox
```

**Ingestion workflow tools (only useful in ingester-style workflows):**
```yaml
- name: ingest_analyze
- name: ingest_format_lookup
- name: ingest_resolve
- name: ingest_run
- name: ingest_format_save
- name: ingest_finalize
- name: ingest_preview
```

`bash` and `python` require `isolation: sandbox` in the runtime block.
Without it, sandbox sessions won't be created and the tools will error.

## Step 4 — Wire delegation (if a parent agent should delegate to this one)

Open the parent agent's `app.yaml` and add to `delegates_to:`:

```yaml
delegates_to:
  - agent: my_agent
    description: "One sentence: when to delegate here and what it does"
    constraints:
      timeout_seconds: 120
      max_tool_rounds: 10
```

`delegates_to:` is the ONLY place delegation edges are declared. Do not
hardcode them in Python.

The director's delegates_to is in:
```
src/remi/application/agents/director/app.yaml
```

## Step 5 — Wire API routes or CLI (only if needed)

Most background agents need no API or CLI surface. Skip this step unless
your agent needs HTTP routes or `remi my_agent` CLI commands.

If needed, edit `src/remi/shell/config/capabilities.py` → `_shell_wiring()`:

```python
_ShellWiring(
    name="my_agent",
    manifest_name="my_agent",     # must match metadata.name in app.yaml
    router_refs=("remi.application.my_slice.api:my_router",),
    cli_ref="remi.application.my_slice.cli:cli_group",
),
```

## Step 6 — Call the agent

**Via API:**
```bash
curl -N -X POST http://localhost:8000/api/v1/agents/my_agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "your input here"}'
```

**Via delegation from another agent (at runtime):**
The parent agent calls `delegate_to_agent(agent="my_agent", task="...")`.

**Via task supervisor (in Python):**
```python
from remi.agent.tasks import TaskSpec
result = await supervisor.spawn_and_wait(
    TaskSpec(
        agent_name="my_agent",
        objective="...",
        input_data={"key": "value"},
    )
)
```

## Runtime stanza — key decisions

```yaml
runtime:
  placement: inline    # inline = same process, required for streaming to user
                       # worker = dispatched to task queue, runs in background
  isolation: none      # none = no sandbox; sandbox = gets bash + python
  durability: ephemeral  # ephemeral = in-memory, no persistence between runs
  resources:
    timeout_seconds: 120    # hard ceiling on total run time
    max_tool_rounds: 10     # how many tool-calling iterations
    max_tokens: 50000       # output token budget
  scaling:
    max_concurrency: 2      # max parallel instances
    queue_priority: normal  # normal | high | critical
```

**Use `inline`** only for chat agents that stream to the user.
**Use `worker`** for background agents (ingestion, research, async tasks).

## Model selection guide

| Model | Use when |
|---|---|
| `claude-haiku-4-5-20251001` | Fast, cheap tasks: ingestion, brief formatting, simple classification |
| `claude-sonnet-4-20250514` | Complex reasoning: director, researcher, multi-step analysis |

Always specify model explicitly in the manifest. Don't rely on defaults.

## Ingestion `context_mode: accumulate`

When `context_mode: accumulate` is set, each step that returns a dict has
its output merged into the shared pipeline context. Downstream steps receive
this merged context as their `args`.

Steps reference prior output with `{steps.<step_id>}` in templates.
Steps can also reference `{context.<key>}` for top-level context values
(including pipeline inputs).

## Common mistakes

**Gate cascades blocking steps that should always run:**
Use `wires:` with `optional: true` to pass output from a gated step to a
downstream step without making the downstream step depend on the gate.

**Agent has bash/python but no sandbox:**
`isolation: sandbox` is required. Without it, the sandbox factory returns a
no-op and tool calls fail silently.

**Delegation edge not found:**
The `agent:` name in `delegates_to:` must exactly match the `metadata.name`
in the target agent's `app.yaml`.

**Agent not discovered:**
The `app.yaml` must live under `src/remi/application/` (any depth).
The `kind:` must be `Agent`, `Pipeline`, or `Workflow` (case-sensitive).
`metadata.name` must be non-empty. Check logs for `manifest_discovered` or
`manifest_missing_name` at startup.
