"""Three foundational, deterministic strategies (ASA-CORE-005).

Pure functions only — no I/O, no randomness, no repository access, no
ranking, no risk management, no capital allocation, no ML. Every function
is a total, deterministic function of its named Indicator inputs and
backing Canonical Facts. Each returns a ``StrategySignal`` when it finds
something actionable, or ``None`` when it does not (a legitimate, common
outcome — Strategies discover, they don't force a result).

**Expected Outcome Metrics are a documented v1 placeholder model.**
ADR-003 requires every Opportunity to carry mandatory, objective Expected
Outcome Metrics (expected_return, maximum_loss, capital_required,
time_horizon_days), and this is the Strategy's own job to compute (ADR-003:
"deterministic outputs of the Strategy's model") — it is not the
portfolio-level risk management or capital allocation this ticket
prohibits (that remains Guardrails'/Ranking's job, per ADR-005 and
ADR-004). But no calibrated financial model exists yet for turning a
signal into dollar-denominated risk/return figures, so this module uses a
single fixed, documented placeholder policy for all three strategies:
- ``capital_required`` = the most recent contributing fact's price
  (cost of a 1-share reference position)
- ``maximum_loss`` = ``-capital_required * STOP_LOSS_FRACTION`` (a fixed
  5% stop-loss assumption)
- ``time_horizon_days`` = a fixed, per-strategy constant

These are placeholders, not calibrated to any backtest, volatility model,
or historical data — tracked as a non-blocking follow-up (see PR for the
linked GitHub Issue).
"""
from __future__ import annotations

from decimal import Decimal, localcontext

from domain.canonical_fact import CanonicalFact
from domain.indicator import Indicator
from domain.outcome_metrics import ExpectedOutcomeMetrics
from indicators.calculations import DECIMAL_PRECISION, extract_price
from strategies.errors import (
    InvalidStrategyParameterError,
    MissingIndicatorInputError,
    NoContributingFactsError,
)
from strategies.signal import StrategySignal

STOP_LOSS_FRACTION = Decimal("0.05")  # v1 placeholder — see module docstring


def _require_indicator(strategy_id: str, indicators: dict[str, Indicator], key: str) -> Indicator:
    if key not in indicators:
        raise MissingIndicatorInputError(strategy_id, key)
    return indicators[key]


def _facts_backing_indicators(
    contributing_indicators: tuple[Indicator, ...], facts: tuple[CanonicalFact, ...],
) -> tuple[CanonicalFact, ...]:
    """Narrow ``facts`` down to exactly those cited by the given indicators'
    ``computed_from`` — never the full caller-supplied candidate set.

    This is what makes Opportunity evidence a *provable* traceability chain
    (Fact -> Indicator -> Opportunity, per ADR-003) rather than an
    unverified echo of whatever facts happened to be passed to
    ``evaluate_strategy``. Mirrors ``indicators/calculations.py``'s
    ``(value, contributing_facts)`` return contract one layer up.
    """
    cited_ids = {
        ref.referenced_id
        for ind in contributing_indicators
        for ref in ind.computed_from
    }
    return tuple(sorted(
        (fact for fact in facts if fact.fact_id in cited_ids),
        key=lambda f: f.fact_id,
    ))


def _most_recent_fact(facts: tuple[CanonicalFact, ...]) -> CanonicalFact:
    return max(facts, key=lambda f: (f.effective_time, f.fact_id))


def _reference_capital_and_loss(
    strategy_id: str, facts: tuple[CanonicalFact, ...],
) -> tuple[Decimal, Decimal]:
    if not facts:
        raise NoContributingFactsError(strategy_id)
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        capital_required = extract_price(_most_recent_fact(facts))
        maximum_loss = -(capital_required * STOP_LOSS_FRACTION)
        return capital_required, maximum_loss


# ---------------------------------------------------------------------------
# moving_average_crossover
# ---------------------------------------------------------------------------

MOVING_AVERAGE_CROSSOVER_TIME_HORIZON_DAYS = 20  # v1 placeholder


def moving_average_crossover(
    indicators: dict[str, Indicator], facts: tuple[CanonicalFact, ...], params: dict,
) -> StrategySignal | None:
    """Bullish crossover: short MA was at/below long MA, now short MA > long MA.

    Required indicator keys: ``short_ma``, ``long_ma`` (current values) and
    ``short_ma_previous``, ``long_ma_previous`` (the immediately prior
    values for the same moving-average pair) — true crossing-event
    detection, not merely "currently above."
    """
    sid = "moving_average_crossover"
    short_ma = _require_indicator(sid, indicators, "short_ma")
    long_ma = _require_indicator(sid, indicators, "long_ma")
    short_prev = _require_indicator(sid, indicators, "short_ma_previous")
    long_prev = _require_indicator(sid, indicators, "long_ma_previous")

    was_at_or_below = short_prev.value <= long_prev.value
    now_above = short_ma.value > long_ma.value
    if not (was_at_or_below and now_above):
        return None

    contributing_indicators = (short_ma, long_ma, short_prev, long_prev)
    backing_facts = _facts_backing_indicators(contributing_indicators, facts)
    capital_required, maximum_loss = _reference_capital_and_loss(sid, backing_facts)
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        expected_return = (short_ma.value - long_ma.value) / long_ma.value

    metrics = ExpectedOutcomeMetrics(
        expected_return=expected_return,
        maximum_loss=maximum_loss,
        capital_required=capital_required,
        time_horizon_days=MOVING_AVERAGE_CROSSOVER_TIME_HORIZON_DAYS,
    )
    return StrategySignal(
        assumptions=(
            "moving_average_crossover v1: bullish crossover detected "
            "(short MA rose from at/below to above long MA)",
            f"maximum_loss uses a fixed {STOP_LOSS_FRACTION} stop-loss placeholder, "
            "not a calibrated risk model",
            f"time_horizon_days is a fixed {MOVING_AVERAGE_CROSSOVER_TIME_HORIZON_DAYS}-day "
            "placeholder, not derived from volatility or backtesting",
        ),
        expected_outcome_metrics=metrics,
        contributing_indicators=contributing_indicators,
        contributing_facts=backing_facts,
    )


# ---------------------------------------------------------------------------
# breakout
# ---------------------------------------------------------------------------

BREAKOUT_TIME_HORIZON_DAYS = 10  # v1 placeholder


def breakout(
    indicators: dict[str, Indicator], facts: tuple[CanonicalFact, ...], params: dict,
) -> StrategySignal | None:
    """Bullish breakout: latest price exceeds the rolling high."""
    sid = "breakout"
    latest_price_ind = _require_indicator(sid, indicators, "latest_price")
    rolling_high_ind = _require_indicator(sid, indicators, "rolling_high")

    if not (latest_price_ind.value > rolling_high_ind.value):
        return None

    contributing_indicators = (latest_price_ind, rolling_high_ind)
    backing_facts = _facts_backing_indicators(contributing_indicators, facts)
    capital_required, maximum_loss = _reference_capital_and_loss(sid, backing_facts)
    with localcontext() as ctx:
        ctx.prec = DECIMAL_PRECISION
        expected_return = (
            (latest_price_ind.value - rolling_high_ind.value) / rolling_high_ind.value
        )

    metrics = ExpectedOutcomeMetrics(
        expected_return=expected_return,
        maximum_loss=maximum_loss,
        capital_required=capital_required,
        time_horizon_days=BREAKOUT_TIME_HORIZON_DAYS,
    )
    return StrategySignal(
        assumptions=(
            "breakout v1: latest price exceeds the rolling high over the "
            "indicator's configured window",
            f"maximum_loss uses a fixed {STOP_LOSS_FRACTION} stop-loss placeholder, "
            "not a calibrated risk model",
            f"time_horizon_days is a fixed {BREAKOUT_TIME_HORIZON_DAYS}-day placeholder, "
            "not derived from volatility or backtesting",
        ),
        expected_outcome_metrics=metrics,
        contributing_indicators=contributing_indicators,
        contributing_facts=backing_facts,
    )


# ---------------------------------------------------------------------------
# momentum
# ---------------------------------------------------------------------------

MOMENTUM_TIME_HORIZON_DAYS = 5  # v1 placeholder


def momentum(
    indicators: dict[str, Indicator], facts: tuple[CanonicalFact, ...], params: dict,
) -> StrategySignal | None:
    """Positive momentum: price_change_percent exceeds a caller-supplied threshold."""
    sid = "momentum"
    pct_change = _require_indicator(sid, indicators, "price_change_percent")

    if "threshold" not in params:
        raise InvalidStrategyParameterError(sid, "missing required parameter 'threshold'")
    threshold = params["threshold"]
    if not isinstance(threshold, Decimal):
        raise InvalidStrategyParameterError(
            sid, f"'threshold' must be a Decimal; got {type(threshold).__name__} {threshold!r}"
        )

    if not (pct_change.value > threshold):
        return None

    contributing_indicators = (pct_change,)
    backing_facts = _facts_backing_indicators(contributing_indicators, facts)
    capital_required, maximum_loss = _reference_capital_and_loss(sid, backing_facts)
    expected_return = pct_change.value

    metrics = ExpectedOutcomeMetrics(
        expected_return=expected_return,
        maximum_loss=maximum_loss,
        capital_required=capital_required,
        time_horizon_days=MOMENTUM_TIME_HORIZON_DAYS,
    )
    return StrategySignal(
        assumptions=(
            f"momentum v1: price_change_percent ({pct_change.value}) exceeds "
            f"threshold ({threshold})",
            f"maximum_loss uses a fixed {STOP_LOSS_FRACTION} stop-loss placeholder, "
            "not a calibrated risk model",
            f"time_horizon_days is a fixed {MOMENTUM_TIME_HORIZON_DAYS}-day placeholder, "
            "not derived from volatility or backtesting",
        ),
        expected_outcome_metrics=metrics,
        contributing_indicators=contributing_indicators,
        contributing_facts=backing_facts,
    )
