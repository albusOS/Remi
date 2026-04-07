"""Template resolution for workflow steps.

Supports three interpolation patterns:
  - ``{input}``           → the original workflow input string
  - ``{steps.<id>}``      → output of a prior step (JSON-serialized if not str)
  - ``{context.<key>}``   → caller-supplied string context values

Promoted from pipeline/runner.py with identical behavior.
"""

from __future__ import annotations

import json
import re

from remi.agent.workflow.types import StepValue

_STEP_REF = re.compile(r"\{steps\.(\w+)\}")
_CTX_REF = re.compile(r"\{context\.(\w+)\}")


def resolve_template(
    template: str,
    workflow_input: str,
    step_outputs: dict[str, StepValue],
    context: dict[str, str] | None = None,
) -> str:
    """Resolve all template references in a string."""
    result = template.replace("{input}", workflow_input)

    for match in _STEP_REF.finditer(template):
        step_id = match.group(1)
        value = step_outputs.get(step_id, "")
        serialized = value if isinstance(value, str) else json.dumps(value, default=str)
        result = result.replace(match.group(0), serialized)

    if context:
        for match in _CTX_REF.finditer(result):
            key = match.group(1)
            result = result.replace(match.group(0), context.get(key, ""))

    return result


def parse_json_output(raw: str) -> StepValue:
    """Best-effort JSON extraction — strips markdown fences if present."""
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)```$", text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, (dict, list)):
            return parsed
        return text
    except (json.JSONDecodeError, TypeError):
        return text
