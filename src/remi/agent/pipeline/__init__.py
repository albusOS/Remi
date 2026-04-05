"""agent/pipeline — generic YAML-driven LLM pipeline executor.

Runs multi-step LLM pipelines (classify → extract → enrich) defined in
``app.yaml`` manifests with ``kind: Pipeline``.  No chat runtime, no
domain knowledge — just sequential LLM calls with template resolution.

Public API::

    from remi.agent.pipeline import IngestionPipelineRunner
"""

from remi.agent.pipeline.runner import IngestionPipelineRunner

__all__ = [
    "IngestionPipelineRunner",
]
