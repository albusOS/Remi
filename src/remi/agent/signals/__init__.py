"""signals — signal system: types, stores, producers, pattern mining, graduation.

Submodules:
  enums        — Severity, RuleCondition, Horizon, Deontic, SignalOutcome, etc.
  tbox         — SignalDefinition, Policy, CausalChain, DomainRulebook, MutableRulebook
  signal       — Signal, ProducerResult, SignalProducer
  feedback     — SignalFeedback, SignalFeedbackSummary
  hypothesis   — Hypothesis, HypothesisKind/Status
  stores       — SignalStore, FeedbackStore, HypothesisStore ABCs
  evaluation   — MakeSignalFn, EntailmentResult, signal_id (entailment primitives)
  composition  — CompositionProducer (co-occurrence signal producer)
  statistical  — StatisticalProducer (anomaly detection over KG)
  composite    — CompositeProducer (pipeline runner for producers)
  pattern      — PatternDetector (hypothesis induction from data)
  graduation   — HypothesisGraduator (promotes hypotheses to TBox)
"""

from remi.agent.graph.types import KnowledgeProvenance as Provenance
from remi.agent.signals.enums import (
    Deontic,
    Horizon,
    HypothesisKind,
    HypothesisStatus,
    RuleCondition,
    Severity,
    SignalOutcome,
)
from remi.agent.signals.feedback import SignalFeedback, SignalFeedbackSummary
from remi.agent.signals.hypothesis import Hypothesis
from remi.agent.signals.signal import ProducerResult, Signal, SignalProducer
from remi.agent.signals.evaluation import EntailmentResult, MakeSignalFn, signal_id
from remi.agent.signals.stores import FeedbackStore, HypothesisStore, SignalStore
from remi.agent.signals.tbox import (
    CausalChain,
    CompositionRule,
    DomainRulebook,
    InferenceRule,
    MutableRulebook,
    Policy,
    SignalDefinition,
    WorkflowSeed,
    WorkflowStep,
)

__all__ = [
    # enums
    "Deontic",
    "Horizon",
    "HypothesisKind",
    "HypothesisStatus",
    "Provenance",
    "RuleCondition",
    "Severity",
    "SignalOutcome",
    # tbox
    "CausalChain",
    "CompositionRule",
    "DomainRulebook",
    "InferenceRule",
    "MutableRulebook",
    "Policy",
    "SignalDefinition",
    "WorkflowSeed",
    "WorkflowStep",
    # signal
    "ProducerResult",
    "Signal",
    "SignalProducer",
    # feedback
    "SignalFeedback",
    "SignalFeedbackSummary",
    # hypothesis
    "Hypothesis",
    # evaluation primitives
    "EntailmentResult",
    "MakeSignalFn",
    "signal_id",
    # stores
    "FeedbackStore",
    "HypothesisStore",
    "SignalStore",
]
