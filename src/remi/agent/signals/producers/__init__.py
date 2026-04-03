"""Signal producers — pluggable signal detection strategies.

- CompositeProducer: pipeline runner that merges multiple producers
- CompositionProducer: co-occurrence detection from existing signals
- StatisticalProducer: anomaly detection over KnowledgeGraph data
"""

from remi.agent.signals.producers.composite import CompositeProducer, CompositeResult
from remi.agent.signals.producers.composition import CompositionProducer
from remi.agent.signals.producers.statistical import StatisticalProducer

__all__ = [
    "CompositeProducer",
    "CompositeResult",
    "CompositionProducer",
    "StatisticalProducer",
]
