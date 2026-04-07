"""pipeline/runner.py — backward-compatible wrapper over the workflow engine.

``IngestionPipelineRunner`` delegates to ``WorkflowRunner`` but preserves
the same public API so existing callers don't need changes.

The loader handles ``kind: Pipeline`` manifests by chaining each step's
``depends_on`` to the previous step, producing a sequential DAG.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from remi.agent.llm.factory import LLMProviderFactory
from remi.agent.llm.types import TokenUsage
from remi.agent.observe.usage import LLMUsageLedger
from remi.agent.workflow.engine import WorkflowRunner
from remi.agent.workflow.loader import load_workflow
from remi.agent.workflow.types import StepValue, WorkflowResult

# ---------------------------------------------------------------------------
# Legacy result types — thin wrappers for backward compat
# ---------------------------------------------------------------------------


@dataclass
class PipelineStepResult:
    """Output from a single pipeline step."""

    step_id: str
    value: StepValue
    usage: TokenUsage


@dataclass
class PipelineResult:
    """Accumulated result from a completed pipeline run."""

    steps: list[PipelineStepResult] = field(default_factory=list)
    total_usage: TokenUsage = field(default_factory=TokenUsage)

    def step(self, step_id: str) -> StepValue | None:
        """Return the parsed output of a named step, or None."""
        for s in self.steps:
            if s.step_id == step_id:
                return s.value
        return None


def _to_pipeline_result(wf: WorkflowResult) -> PipelineResult:
    """Convert a WorkflowResult to the legacy PipelineResult shape."""
    return PipelineResult(
        steps=[
            PipelineStepResult(step_id=sr.step_id, value=sr.value, usage=sr.usage)
            for sr in wf.steps
        ],
        total_usage=wf.total_usage,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class IngestionPipelineRunner:
    """Backward-compatible pipeline runner — delegates to WorkflowRunner.

    Callers see the same ``run()`` → ``PipelineResult`` API. Internally,
    the workflow engine handles DAG scheduling, parallel execution, etc.
    """

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        default_provider: str,
        default_model: str,
        usage_ledger: LLMUsageLedger | None = None,
    ) -> None:
        self._runner = WorkflowRunner(
            provider_factory=provider_factory,
            default_provider=default_provider,
            default_model=default_model,
            usage_ledger=usage_ledger,
        )

    async def run(
        self,
        pipeline_name: str,
        pipeline_input: str,
        *,
        context: dict[str, str] | None = None,
        skip_steps: set[str] | None = None,
    ) -> PipelineResult:
        """Execute the named pipeline and return the accumulated result."""
        workflow = load_workflow(pipeline_name)
        wf_result = await self._runner.run(
            workflow,
            pipeline_input,
            context=context,
            skip_steps=skip_steps,
        )
        return _to_pipeline_result(wf_result)
