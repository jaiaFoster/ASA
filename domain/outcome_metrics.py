"""Expected Outcome Metrics (ADR-003 as amended by ASA-CORE-001).

Units, semantics, and the mandatory/optional split are fixed here at the
domain-model level, per the amended ADR-003 (ASA-CORE-001A). Structural
definitions and identity invariants only — no calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.values import DomainInvariantError, require_unit_interval


@dataclass(frozen=True, slots=True)
class ExpectedOutcomeMetrics:
    """Standardized financial characteristics of an Opportunity.

    Every Strategy produces these for every Opportunity it emits, in this
    common Strategy-independent vocabulary; Ranking compares Opportunities
    using these metrics (ADR-003 as amended). They are objective outputs of
    the Strategy's model applied to cited Evidence — never a subjective
    confidence score.

    Units and semantics (ASA-CORE-001A):

    - ``expected_return`` — **mandatory**. Expected profit or loss over the
      Opportunity's horizon, as a signed decimal fraction of
      ``capital_required`` (``Decimal("0.12")`` = +12%). Not annualized.
    - ``maximum_loss`` — **mandatory**. Worst-case loss in account currency
      (USD), expressed as a **non-positive** amount (``Decimal("-200")`` =
      $200 at risk). ``0`` means no capital can be lost.
    - ``capital_required`` — **mandatory**. Capital in USD that must be
      committed or reserved to enter the position; **non-negative**.
    - ``maximum_gain`` — optional (None where unbounded or not meaningful).
      Best-case profit in USD; **non-negative**.
    - ``probability_of_profit`` — optional. Model-derived probability the
      position closes profitable, in **[0, 1]**.
    - ``time_horizon_days`` — optional. Expected holding period in whole
      calendar days; **positive** when present.

    A metric that is not meaningful for a given Strategy is None — never a
    fabricated value. Mandatory metrics can never be None: an Opportunity
    with an empty comparison payload cannot be ranked and is structurally
    invalid (see also ADR-003's "complete Strategy" discipline note).
    """

    expected_return: Decimal
    maximum_loss: Decimal
    capital_required: Decimal
    maximum_gain: Decimal | None = None
    probability_of_profit: Decimal | None = None
    time_horizon_days: int | None = None

    def __post_init__(self) -> None:
        owner = "ExpectedOutcomeMetrics"
        for name in ("expected_return", "maximum_loss", "capital_required"):
            if getattr(self, name) is None:
                raise DomainInvariantError(f"{owner}.{name} is mandatory and cannot be None")
        if self.maximum_loss > 0:
            raise DomainInvariantError(
                f"{owner}.maximum_loss is a loss and must be <= 0; got {self.maximum_loss!r}"
            )
        if self.capital_required < 0:
            raise DomainInvariantError(
                f"{owner}.capital_required must be >= 0; got {self.capital_required!r}"
            )
        if self.maximum_gain is not None and self.maximum_gain < 0:
            raise DomainInvariantError(
                f"{owner}.maximum_gain must be >= 0 when present; got {self.maximum_gain!r}"
            )
        if self.probability_of_profit is not None:
            require_unit_interval(self.probability_of_profit, owner, "probability_of_profit")
        if self.time_horizon_days is not None and self.time_horizon_days < 1:
            raise DomainInvariantError(
                f"{owner}.time_horizon_days must be positive when present; "
                f"got {self.time_horizon_days!r}"
            )
