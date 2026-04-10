"""Template resolution and condition evaluation for workflow steps.

Template interpolation patterns:
  - ``{input}``                    → the original workflow input string
  - ``{steps.<id>}``              → output of a prior step (JSON-serialized if not str)
  - ``{steps.<id>.<field>}``      → nested field from a prior step's dict output
  - ``{context.<key>}``           → caller-supplied string context values

Condition evaluation (used by gate steps and inline ``when``):
  - ``steps.classify``                 → truthiness check
  - ``steps.classify.confidence > 0.5`` → numeric comparison
"""

from __future__ import annotations

import json
import re
from typing import Any

from remi.agent.workflow.types import StepValue

_STEP_REF = re.compile(r"\{steps\.(\w+(?:\.\w+)*)\}")
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
    """Resolve all template references in a string.

    Supports nested dot-paths: ``{steps.extract.column_map}`` resolves
    ``step_outputs["extract"]["column_map"]``.
    """
    result = template.replace("{input}", workflow_input)

    for match in _STEP_REF.finditer(template):
        dot_path = match.group(1)
        value = _resolve_dot_path(dot_path, step_outputs)
        if value is None:
            value = ""
        serialized = value if isinstance(value, str) else json.dumps(value, default=str)
        result = result.replace(match.group(0), serialized)

    if context:
        for match in _CTX_REF.finditer(result):
            key = match.group(1)
            result = result.replace(match.group(0), context.get(key, ""))

    return result


def parse_json_output(raw: str) -> StepValue:
    """Best-effort JSON extraction from LLM output.

    Tries in order:
      1. Direct JSON parse of the full text
      2. Extract from markdown fences (```json ... ```)
      3. Find the first ``{`` … last ``}`` and parse that substring
    """
    text = raw.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            parsed = json.loads(fence.group(1).strip())
            if isinstance(parsed, (dict, list)):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            parsed = json.loads(text[first_brace : last_brace + 1])
            if isinstance(parsed, (dict, list)):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return text


# ---------------------------------------------------------------------------
# Condition evaluation — shared by gate steps and inline ``when``
# ---------------------------------------------------------------------------


def evaluate_condition(
    condition: str,
    step_outputs: dict[str, StepValue],
    pipeline_ctx: dict[str, Any] | None = None,
) -> bool:
    """Evaluate a condition expression against prior step outputs.

    Dot-path truthiness::

        steps.classify            → bool(step_outputs["classify"])
        steps.extract.has_data    → bool(step_outputs["extract"]["has_data"])

    Negation::

        not steps.format_lookup.match  → not bool(step_outputs["format_lookup"]["match"])

    Numeric comparisons::

        steps.classify.confidence > 0.5
        steps.extract.row_count >= 10
    """
    if not condition:
        return True

    path = condition.strip()

    negate = False
    if path.startswith("not "):
        negate = True
        path = path[4:].strip()

    for op_str, op_fn in (
        (">=", lambda a, b: a >= b),
        ("<=", lambda a, b: a <= b),
        (">", lambda a, b: a > b),
        ("<", lambda a, b: a < b),
    ):
        if op_str in path:
            left, right = path.split(op_str, 1)
            left_val = _resolve_path(left.strip(), step_outputs, pipeline_ctx)
            try:
                right_num = float(right.strip())
                left_num = float(left_val) if left_val is not None else 0.0
                result = op_fn(left_num, right_num)
                return (not result) if negate else result
            except (ValueError, TypeError):
                return negate

    result = bool(_resolve_path(path, step_outputs, pipeline_ctx))
    return (not result) if negate else result


def _resolve_path(
    path: str,
    step_outputs: dict[str, StepValue],
    pipeline_ctx: dict[str, Any] | None = None,
) -> Any:
    """Resolve a path against step outputs or the pipeline context.

    ``context.field`` resolves against the pipeline context dict.
    Everything else falls through to ``_resolve_dot_path``.
    """
    if path.startswith("context.") and pipeline_ctx is not None:
        field = path[8:]
        parts = field.split(".")
        current: Any = pipeline_ctx
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
    return _resolve_dot_path(path, step_outputs)


def _resolve_dot_path(
    path: str,
    step_outputs: dict[str, StepValue],
) -> Any:
    """Resolve a dot-path like ``steps.extract.column_map`` to a nested value.

    Walks ``step_outputs[step_id][field1][field2]…`` for arbitrary depth.
    """
    if path.startswith("steps."):
        path = path[6:]

    parts = path.split(".")
    step_id = parts[0]
    current: Any = step_outputs.get(step_id)

    for part in parts[1:]:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None

    return current
