"""Strategy calculation return contract (ASA-CORE-005).

Every registered strategy calculation returns a ``StrategySignal`` (or
``None`` when it finds nothing actionable this cycle — a legitimate,
common outcome; Strategies *discover*, they don't force a result). The
engine (``strategies/engine.py``) wraps a triggered signal into a full,
immutable ``Opportunity`` — one calculation, one home: a strategy function
never constructs an ``Opportunity`` or computes an identity itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.canonical_fact import CanonicalFact
from domain.indicator import Indicator
from domain.outcome_metrics import ExpectedOutcomeMetrics


@dataclass(frozen=True)
class StrategySignal:
    """One strategy calculation's output for one evaluation cycle.

    ``contributing_indicators``/``contributing_facts`` are exactly the
    Indicator/Canonical Fact objects the calculation actually used —
    mirrors ``indicators/calculations.py``'s ``(value, contributing_facts)``
    return contract, so the engine can build complete, accurate provenance
    rather than citing a caller-supplied candidate set that may be broader
    than what was used.
    """

    assumptions: tuple[str, ...]
    expected_outcome_metrics: ExpectedOutcomeMetrics
    contributing_indicators: tuple[Indicator, ...]
    contributing_facts: tuple[CanonicalFact, ...]
