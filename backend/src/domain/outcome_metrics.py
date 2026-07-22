"""Expected Outcome Metrics (ADR-003 as amended by ASA-CORE-001).

Units, semantics, and the mandatory/optional split are fixed here at the
domain-model level (ASA-CORE-001A, tightened by ASA-CORE-002). Structural
definitions and identity invariants only — no calculations.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.values import (
    DomainInvariantError,
    require_finite_decimal,
    require_positive,
    require_unit_interval,
)


@dataclass(frozen=True, slots=True)
class ExpectedOutcomeMetrics:
    """Standardized financial characteristics of an Opportunity.

    Every Strategy produces these for every Opportunity it emits, in this
    common Strategy-independent vocabulary; Ranking compares Opportunities
    using these metrics (ADR-003 as amended). They are objective outputs of
    the Strategy's model applied to cited Evidence — never a subjective
    confidence score.

    Units and semantics (ASA-CORE-001A / ASA-CORE-002):

    - ``expected_return`` — **mandatory** finite ``Decimal``. Expected profit
      or loss over ``time_horizon_days``, as a signed decimal fraction of
      ``capital_required`` (``Decimal("0.12")`` = +12%). Not annualized.
    - ``maximum_loss`` — **mandatory** finite ``Decimal``. Worst-case loss in
      account currency (USD), expressed as a **non-positive** amount
      (``Decimal("-200")`` = $200 at risk). ``0`` means no capital can be lost.
    - ``capital_required`` — **mandatory** finite ``Decimal``. Capital in USD
      that must be committed or reserved to enter the position; non-negative.
    - ``time_horizon_days`` — **mandatory** exact positive ``int`` (bool is
      rejected). The measurement period, in whole calendar days, over which
      ``expected_return`` applies. Mandatory because expected return is
      horizon-dependent and cannot be compared by Ranking without a known
      measurement period (ASA-CORE-002).
    - ``maximum_gain`` — optional finite ``Decimal`` (None where unbounded or
      not meaningful). Best-case profit in USD; non-negative.
    - ``probability_of_profit`` — optional finite ``Decimal``. Model-derived
      probability the position closes profitable, in **[0, 1]**.

    All financial metrics are ``Decimal`` — ``float``, ``int``, and ``bool``
    are rejected at construction. An optional metric that is not meaningful
    for a given Strategy is None — never a fabricated value.
    """

    expected_return: Decimal
    maximum_loss: Decimal
    capital_required: Decimal
    time_horizon_days: int
    maximum_gain: Decimal | None = None
    probability_of_profit: Decimal | None = None

    def __post_init__(self) -> None:
        owner = "ExpectedOutcomeMetrics"
        for name in ("expected_return", "maximum_loss", "capital_required"):
            value = getattr(self, name)
            if value is None:
                raise DomainInvariantError(f"{owner}.{name} is mandatory and cannot be None")
            require_finite_decimal(value, owner, name)
        if self.time_horizon_days is None:
            raise DomainInvariantError(
                f"{owner}.time_horizon_days is mandatory and cannot be None"
            )
        require_positive(self.time_horizon_days, owner, "time_horizon_days")
        if self.maximum_loss > 0:
            raise DomainInvariantError(
                f"{owner}.maximum_loss is a loss and must be <= 0; got {self.maximum_loss!r}"
            )
        if self.capital_required < 0:
            raise DomainInvariantError(
                f"{owner}.capital_required must be >= 0; got {self.capital_required!r}"
            )
        if self.maximum_gain is not None:
            require_finite_decimal(self.maximum_gain, owner, "maximum_gain")
            if self.maximum_gain < 0:
                raise DomainInvariantError(
                    f"{owner}.maximum_gain must be >= 0 when present; "
                    f"got {self.maximum_gain!r}"
                )
        if self.probability_of_profit is not None:
            require_finite_decimal(self.probability_of_profit, owner, "probability_of_profit")
            require_unit_interval(self.probability_of_profit, owner, "probability_of_profit")
