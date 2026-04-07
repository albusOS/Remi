"""Template resolution and condition evaluation for workflow steps.

Template interpolation patterns:
  - ``{input}``           → the original workflow input string
  - ``{steps.<id>}``      → output of a prior step (JSON-serialized if not str)
  - ``{context.<key>}``   → caller-supplied string context values

Condition evaluation (used by gate steps and inline ``when``):
  - ``steps.classify``                 → truthiness check
  - ``steps.classify.confidence > 0.5`` → numeric comparison
"""

from __future__ import annotations

import json
import re
from typing import Any

from remi.agent.workflow.types import StepValue

_STEP_REF = re.compile(r"\{steps\.(\w+)\}")
_CTX_REF = re.compile(r"\{context\.(\w+)\}")


# ---------------------------------------------------------------------------
# Template resolution
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Condition evaluation — shared by gate steps and inline ``when``
# ---------------------------------------------------------------------------


def evaluate_condition(
    condition: str,
    step_outputs: dict[str, StepValue],
) -> bool:
    """Evaluate a condition expression against prior step outputs.

    Dot-path truthiness::

        steps.classify            → bool(step_outputs["classify"])
        steps.extract.has_data    → bool(step_outputs["extract"]["has_data"])

    Numeric comparisons::

        steps.classify.confidence > 0.5
        steps.extract.row_count >= 10
    """
    if not condition:
        return True

    path = condition.strip()

    for op_str, op_fn in (
        (">=", lambda a, b: a >= b),
        ("<=", lambda a, b: a <= b),
        (">", lambda a, b: a > b),
        ("<", lambda a, b: a < b),
    ):
        if op_str in path:
            left, right = path.split(op_str, 1)
            left_val = _resolve_dot_path(left.strip(), step_outputs)
            try:
                right_num = float(right.strip())
                left_num = float(left_val) if left_val is not None else 0.0
                return op_fn(left_num, right_num)
            except (ValueError, TypeError):
                return False

    return bool(_resolve_dot_path(path, step_outputs))


def _resolve_dot_path(
    path: str,
    step_outputs: dict[str, StepValue],
) -> Any:
    """Resolve a dot-path like ``steps.classify.confidence``."""
    if path.startswith("steps."):
        path = path[6:]

    parts = path.split(".", 1)
    step_id = parts[0]
    value = step_outputs.get(step_id)

    if value is None:
        return None

    if len(parts) == 1:
        return value

    field = parts[1]
    if isinstance(value, dict):
        return value.get(field)

    return value
