"""agent/pipeline — backward-compatible wrapper over agent/workflow.

This package is deprecated. Use ``agent/workflow`` directly for new code.
``IngestionPipelineRunner`` is a thin adapter that delegates to
``WorkflowRunner``.

Public API::

    from remi.agent.pipeline import IngestionPipelineRunner
"""

from remi.agent.pipeline.runner import IngestionPipelineRunner

__all__ = [
    "IngestionPipelineRunner",
]
