"""Expected Outcome Metrics (ADR-003 as amended by ASA-CORE-001).

Structural definitions only — no business logic (ASA-CORE-001).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ExpectedOutcomeMetrics:
    """Standardized financial characteristics of an Opportunity.

    Every Strategy produces these for every Opportunity it emits, in this
    common Strategy-independent vocabulary; Ranking compares Opportunities
    using these metrics (ADR-003 as amended). They are objective outputs of
    the Strategy's model applied to cited Evidence — never a subjective
    confidence score. A metric that is not meaningful for a given Strategy
    is None, never a fabricated value.
    """

    expected_return: Decimal | None
    maximum_gain: Decimal | None
    maximum_loss: Decimal | None
    capital_required: Decimal | None
    probability_of_profit: Decimal | None
    time_horizon_days: int | None
