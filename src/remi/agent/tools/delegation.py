"""Agent delegation tool — structured task-based multi-agent coordination.

The ``delegate_to_agent`` tool gives a parent agent the ability to dispatch
work to any named agent via the kernel's task supervisor. The specialist
runs a complete agent loop (with its own tools, sandbox session, and
iteration budget) under supervised lifecycle management.

Delegation edges are declared in each agent's YAML manifest under
``delegates_to:``. The ``Workforce`` model assembles these edges into
a per-parent allowlist at startup. At execution time the tool reads
``caller_agent`` from the merged args (injected by the tool executor)
and resolves the calling agent's allowlist via ``Workforce.get_delegates``.

The tool creates a ``TaskSpec``, submits it to the ``TaskSupervisor``,
and awaits the ``TaskResult``. This provides:
  - Per-parent delegation scoping (each agent can only spawn its declared children)
  - Structured input/output (not raw string passing)
  - Lifecycle tracking (spawned → running → done/failed/cancelled)
  - Budget constraints from ``DelegateRef.constraints`` in YAML
  - Trace correlation (parent_run_id propagation)
  - Domain event publication (task.spawned, task.completed, task.failed)
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.observe.types import get_current_trace_id
from remi.agent.tasks import TaskConstraints, TaskSpec, TaskSupervisor
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry
from remi.agent.workforce import Workforce

logger = structlog.get_logger("remi.agent.tools.delegation")


class DelegationToolProvider(ToolProvider):
    """Registers the ``delegate_to_agent`` tool scoped by the Workforce graph.

    The workforce carries per-parent delegation edges read from YAML.
    At execution time the tool resolves the caller's allowlist, enforces
    it, and applies ``DelegateRef.constraints`` as the task budget.
    """

    def __init__(
        self,
        supervisor: TaskSupervisor,
        workforce: Workforce,
    ) -> None:
        self._supervisor = supervisor
        self._workforce = workforce

    def register(self, registry: ToolRegistry) -> None:
        workforce = self._workforce
        supervisor = self._supervisor

        async def delegate_to_agent(args: dict[str, Any]) -> Any:
            agent_name = args.get("agent_name", "")
            task = args.get("task", "")
            context = args.get("context", "")
            timeout = args.get("timeout")
            caller = args.get("caller_agent", "")

            if not agent_name:
                return {"error": "agent_name is required"}
            if not task:
                return {"error": "task is required"}

            allowed = workforce.get_delegates(caller)
            if not allowed:
                all_names = [
                    name for name, desc in workforce.agents.items()
                    if desc.audience != "user"
                ]
                allowed = {n: "" for n in all_names}

            if agent_name not in allowed:
                return {
                    "error": f"Agent '{caller}' cannot delegate to '{agent_name}'",
                    "allowed_delegates": list(allowed.keys()),
                }

            delegate_ref = workforce.get_delegate_ref(caller, agent_name)
            ref_c = delegate_ref.constraints if delegate_ref else None

            constraints = TaskConstraints(
                timeout_seconds=(
                    float(timeout) if timeout
                    else (ref_c.timeout_seconds if ref_c else None)
                ),
                max_tool_rounds=ref_c.max_tool_rounds if ref_c else None,
                max_tokens=ref_c.max_tokens if ref_c else None,
                allowed_tools=ref_c.allowed_tools if ref_c else None,
            )

            input_data: dict[str, Any] = {}
            if context:
                input_data["parent_context"] = context

            spec = TaskSpec(
                agent_name=agent_name,
                objective=task,
                input_data=input_data,
                constraints=constraints,
                parent_run_id=get_current_trace_id() or "",
                metadata={"source": "delegate_to_agent", "caller": caller},
            )

            logger.info(
                "delegate_to_agent",
                caller=caller,
                agent_name=agent_name,
                task_length=len(task),
                has_context=bool(context),
                has_timeout=timeout is not None,
            )

            result = await supervisor.spawn_and_wait(spec)

            if not result.ok:
                return {
                    "error": result.error or "Task failed",
                    "agent_name": agent_name,
                    "task_id": result.run_id,
                }

            return {
                "agent_name": agent_name,
                "run_id": result.run_id,
                "response": result.output or "",
            }

        all_agent_descriptions = "\n".join(
            f"  - **{name}**: {desc.description}"
            for name, desc in workforce.agents.items()
            if desc.audience != "user"
        )

        registry.register(
            "delegate_to_agent",
            delegate_to_agent,
            ToolDefinition(
                name="delegate_to_agent",
                description=(
                    "Delegate a task to a specialist agent. "
                    "The specialist runs autonomously with its own tools and "
                    "returns its output. Use this for tasks that require deep "
                    "analysis, structured research, or specialized workflows.\n\n"
                    f"Available specialist agents:\n{all_agent_descriptions}"
                ),
                args=[
                    ToolArg(
                        name="agent_name",
                        description="Name of the specialist agent to invoke.",
                        required=True,
                    ),
                    ToolArg(
                        name="task",
                        description=(
                            "The task or question to delegate. Be specific — the "
                            "specialist has no context from your conversation unless "
                            "you provide it."
                        ),
                        required=True,
                    ),
                    ToolArg(
                        name="context",
                        description=(
                            "Optional context to pass to the specialist: relevant "
                            "data, constraints, or prior findings from your analysis."
                        ),
                    ),
                    ToolArg(
                        name="timeout",
                        description=(
                            "Optional timeout in seconds. The task will be cancelled "
                            "if it exceeds this duration."
                        ),
                    ),
                ],
            ),
        )
