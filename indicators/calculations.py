"""Six foundational, deterministic price indicator calculations (ASA-CORE-004).

Pure functions only — no I/O, no randomness, no repository access. Every
function is a total, deterministic function of its Canonical Fact input,
using ``decimal.Decimal`` throughout (never ``float``) so precision is
preserved and results are byte-identical across replays regardless of the
caller's ambient decimal context (each function pins its own context via
``decimal.localcontext``).

**Return contract.** Every function returns ``(value, contributing_facts)``
— the calculated value *and* the exact subset of the input facts actually
used to produce it (e.g. a 3-period SMA over 5 candidate facts cites only
the 3 it averaged, not all 5 passed in). This is what lets
``indicators/engine.py`` build provenance that reflects true, complete
lineage rather than the full candidate set the caller happened to supply.

**v1 assumption — price-shaped facts only.** Every calculation here reads
a fact's resolved value as an immutable mapping (tuple of ``(str, value)``
pairs — see ``domain/values.py``) containing a ``"price"`` key, matching
the synthetic provider's ``market_price`` fact shape (ASA-CORE-002/003).
There is no general per-fact-type value-projection contract yet; this
module hardcodes the "price" key. Tracked as a non-blocking follow-up (see
PR for the linked GitHub Issue) — all six required indicators are
price-based, so this is sufficient for this ticket's scope, not a
shortcut around it.

All functions sort their input facts by ``(effective_time, fact_id)``
before computing, so results never depend on the order facts are supplied
in — required for "deterministic execution order" / order-independent
replay.
"""
from __future__ import annotations

from decimal import Decimal, localcontext

from domain.canonical_fact import CanonicalFact
from indicators.errors import (
    IndicatorCalculationError,
    InconsistentFactGroupError,
    InsufficientDataError,
)

DECIMAL_PRECISION = 28  # explicit, pinned — independent of ambient decimal context

CalculationResult = tuple[object, tuple[CanonicalFact, ...]]


def _extract_price(fact: CanonicalFact) -> Decimal:
    """Extract the ``"price"`` field from a fact's immutable mapping value."""
    if not isinstance(fact.value, tuple):
        raise IndicatorCalculationError(
            f"fact {fact.fact_id} value is not a mapping; cannot extract price"
        )
    as_dict = dict(fact.value)
    price = as_dict.get("price")
    if not isinstance(price, Decimal):
        raise IndicatorCalculationError(
            f"fact {fact.fact_id} has no Decimal 'price' field to derive an indicator from"
        )
    return price


def _sorted_consistent(facts: tuple[CanonicalFact, ...]) -> tuple[CanonicalFact, ...]:
    """Sort facts deterministically; require a single shared fact_type."""
    if not facts:
        return facts
    fact_type = facts[0].fact_type
    for fact in facts[1:]:
        if fact.fact_type != fact_type:
            raise InconsistentFactGroupError(
                f"mixed fact_type in indicator input: "
                f"{fact_type!r} vs {fact.fact_type!r}"
            )
    return tuple(sorted(facts, key=lambda f: (f.effective_time, f.fact_id)))


def _require_min_facts(indicator_type: str, facts: tuple[CanonicalFact, ...],
                        minimum: int) -> None:
    if len(facts) < minimum:
        raise InsufficientDataError(indicator_type, minimum, len(facts))


# ---------------------------------------------------------------------------
# latest_price
# ---------------------------------------------------------------------------

def latest_price(facts: tuple[CanonicalFact, ...], params: dict) -> CalculationResult:
    """Most recent fact's price (by effective_time, then fact_id as tiebreak)."""
    ordered = _sorted_consistent(facts)
    _require_min_facts("latest_price", ordered, 1)
    contributing = (ordered[-1],)
    return _extract_price(ordered[-1]), contributing


# ---------------------------------------------------------------------------
# price_change_percent
# ---------------------------------------------------------------------------

def price_change_percent(facts: tuple[CanonicalFact, ...], params: dict) -> CalculationResult:
    """Percent change from the second-most-recent to the most-recent price.

    ``(current - previous) / previous``, as a signed decimal fraction
    (matching ``ExpectedOutcomeMetrics.expected_return``'s convention).
    """
    ordered = _sorted_consistent(facts)
    _require_min_facts("price_change_percent", ordered, 2)
    contributing = (ordered[-2], ordered[-1])
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        previous = _extract_price(ordered[-2])
        current = _extract_price(ordered[-1])
        if previous == 0:
            raise IndicatorCalculationError(
                "price_change_percent: previous price is zero, percent change undefined"
            )
        return (current - previous) / previous, contributing


# ---------------------------------------------------------------------------
# simple_moving_average
# ---------------------------------------------------------------------------

def simple_moving_average(facts: tuple[CanonicalFact, ...], params: dict) -> CalculationResult:
    """Arithmetic mean of the last ``params["period"]`` facts' prices."""
    period = params["period"]
    ordered = _sorted_consistent(facts)
    _require_min_facts("simple_moving_average", ordered, period)
    window = ordered[-period:]
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        total = sum((_extract_price(f) for f in window), Decimal(0))
        return total / Decimal(period), window


# ---------------------------------------------------------------------------
# exponential_moving_average
# ---------------------------------------------------------------------------

def exponential_moving_average(facts: tuple[CanonicalFact, ...], params: dict) -> CalculationResult:
    """Standard EMA: seeded with the SMA of the first ``period`` facts, then
    applied over the remaining facts in chronological order.

    ``multiplier = 2 / (period + 1)``; ``ema = (price - ema) * multiplier + ema``.
    Contributing facts are the *entire* ordered input (all facts feed the
    running average, unlike SMA/rolling_high/low's fixed trailing window).
    """
    period = params["period"]
    ordered = _sorted_consistent(facts)
    _require_min_facts("exponential_moving_average", ordered, period)
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        seed_window = ordered[:period]
        ema = sum((_extract_price(f) for f in seed_window), Decimal(0)) / Decimal(period)
        multiplier = Decimal(2) / Decimal(period + 1)
        for fact in ordered[period:]:
            price = _extract_price(fact)
            ema = (price - ema) * multiplier + ema
        return ema, ordered


# ---------------------------------------------------------------------------
# rolling_high / rolling_low
# ---------------------------------------------------------------------------

def rolling_high(facts: tuple[CanonicalFact, ...], params: dict) -> CalculationResult:
    """Maximum price over the last ``params["period"]`` facts."""
    period = params["period"]
    ordered = _sorted_consistent(facts)
    _require_min_facts("rolling_high", ordered, period)
    window = ordered[-period:]
    return max(_extract_price(f) for f in window), window


def rolling_low(facts: tuple[CanonicalFact, ...], params: dict) -> CalculationResult:
    """Minimum price over the last ``params["period"]`` facts."""
    period = params["period"]
    ordered = _sorted_consistent(facts)
    _require_min_facts("rolling_low", ordered, period)
    window = ordered[-period:]
    return min(_extract_price(f) for f in window), window
