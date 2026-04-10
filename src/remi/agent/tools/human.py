"""ask_human — a first-class tool for pausing a task until a human answers.

When an agent genuinely cannot determine something from the data, it
calls ``ask_human`` with structured questions. The tool:

1. Validates and converts the questions into ``HumanQuestion`` objects.
2. Asks the ``TaskSupervisor`` to suspend the current task.
3. Blocks (via ``task.wait_for_human()``) until the human supplies answers.
4. Returns the answers to the agent so it can continue with confidence.

The frontend subscribes to ``task.waiting_on_human`` events via the
WebSocket event feed and renders the questions inline.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.tasks.spec import HumanQuestion, HumanQuestionOption
from remi.agent.tasks.supervisor import TaskSupervisor
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry

logger = structlog.get_logger(__name__)


class HumanToolProvider(ToolProvider):
    """Registers the ``ask_human`` tool on the agent tool registry."""

    def __init__(self, supervisor: TaskSupervisor) -> None:
        self._supervisor = supervisor

    def register(self, registry: ToolRegistry, *, namespace: str = "") -> None:
        supervisor = self._supervisor

        async def ask_human(args: dict[str, Any]) -> Any:
            task_id = args.get("_task_id", "")
            if not task_id:
                return {"error": "ask_human requires a running task context (_task_id)"}

            raw_questions = args.get("questions")
            if not raw_questions:
                return {"error": "questions is required"}

            if isinstance(raw_questions, str):
                import json

                try:
                    raw_questions = json.loads(raw_questions)
                except json.JSONDecodeError:
                    return {"error": "questions must be a valid JSON array"}

            questions: list[HumanQuestion] = []
            for q in raw_questions:
                options = [
                    HumanQuestionOption(id=o["id"], label=o["label"])
                    for o in (q.get("options") or [])
                ]
                questions.append(
                    HumanQuestion(
                        id=q["id"],
                        prompt=q["prompt"],
                        kind=q.get("kind", "select"),
                        options=options,
                        default=q.get("default"),
                        required=q.get("required", True),
                    )
                )

            task = supervisor.get_task(task_id)
            if task is None:
                return {"error": f"Task {task_id} not found"}

            suspended = await supervisor.suspend_for_human(task_id, questions)
            if not suspended:
                return {"error": f"Task {task_id} could not be suspended (status: {task.status.value})"}

            logger.info(
                "ask_human_waiting",
                task_id=task_id,
                question_count=len(questions),
            )

            answers = await task.wait_for_human()

            logger.info(
                "ask_human_answered",
                task_id=task_id,
                answer_keys=list(answers.keys()),
            )

            return {"answers": answers}

        registry.register(
            "ask_human",
            ask_human,
            ToolDefinition(
                name="ask_human",
                description=(
                    "Pause the current task and ask the user a question. "
                    "Use this when you genuinely cannot determine something "
                    "from the data — e.g. which manager a report belongs to, "
                    "or whether a column mapping is correct. The task will "
                    "suspend until the user answers. Returns the user's answers."
                ),
                args=[
                    ToolArg(
                        name="questions",
                        description=(
                            'JSON array of questions. Each: {"id": "manager", '
                            '"kind": "select"|"text"|"confirm", '
                            '"prompt": "Which manager?", '
                            '"options": [{"id": "alex", "label": "Alex Budavich"}, ...]}'
                        ),
                        required=True,
                        type="array",
                    ),
                ],
            ),
            namespace=namespace,
        )
