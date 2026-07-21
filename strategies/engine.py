"""Deterministic Strategy engine (ASA-CORE-005).

Evaluates Canonical Facts and Indicators via the strategy registry
(``strategies/registry.py``) to produce immutable ``Opportunity`` objects.
Pure orchestration — no repository access, no randomness, no ranking, no
broker/provider access, no persistence. A total, deterministic function of
its arguments, making Opportunity generation fully replayable. Strategies
express opportunity generation only: this engine never ranks, filters,
manages risk, or allocates capital across Opportunities — a triggered
signal always becomes exactly one returned Opportunity, or none at all.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from domain.canonical_fact import CanonicalFact
from domain.canonicalization import serialize_canonical
from domain.indicator import Indicator
from domain.opportunity import Opportunity, RecommendationState
from domain.operational import Instrument
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.references import Confidence, EvidenceKind, EvidenceReference
from domain.values import require_tz_aware
from strategies.registry import DEFAULT_REGISTRY, StrategyRegistry

OPPORTUNITY_IDENTITY_NAMESPACE = "asa.opportunity"
OPPORTUNITY_IDENTITY_VERSION = "v2"


def _metrics_as_normalized_value(
    metrics: ExpectedOutcomeMetrics,
) -> tuple[tuple[str, object], ...]:
    return (
        ("capital_required", metrics.capital_required),
        ("expected_return", metrics.expected_return),
        ("maximum_gain", metrics.maximum_gain),
        ("maximum_loss", metrics.maximum_loss),
        ("probability_of_profit", metrics.probability_of_profit),
        ("time_horizon_days", metrics.time_horizon_days),
    )


def opportunity_identity(
    strategy_id: str,
    instrument: Instrument,
    source_indicator_ids: tuple[str, ...],
    source_fact_ids: tuple[str, ...],
    effective_time: datetime,
    expected_outcome_metrics: ExpectedOutcomeMetrics,
) -> str:
    """Deterministic, versioned Opportunity identity (algorithm v1).

    Inputs: strategy_id, canonical instrument identity, source indicator ids,
    source fact ids, effective time, and expected outcome metrics — mirroring
    ``indicators.engine.indicator_identity``'s and
    ``reconciliation.rules.fact_identity``'s algorithm style under a
    distinct namespace. No UUIDs, no sequence numbers, no insertion time,
    no randomness. Content-addressed: including both source indicator and
    fact ids means two evaluations over different evidence that happen to
    produce the same metrics do not collide.
    """
    require_tz_aware(effective_time, "opportunity_identity", "effective_time")
    payload = "\n".join(
        (
            OPPORTUNITY_IDENTITY_NAMESPACE,
            OPPORTUNITY_IDENTITY_VERSION,
            serialize_canonical(strategy_id),
            serialize_canonical((instrument.identity.scheme, instrument.identity.value)),
            serialize_canonical(tuple(sorted(source_indicator_ids))),
            serialize_canonical(tuple(sorted(source_fact_ids))),
            serialize_canonical(effective_time),
            serialize_canonical(_metrics_as_normalized_value(expected_outcome_metrics)),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_strategy(
    strategy_id: str,
    indicators: dict[str, Indicator],
    facts: tuple[CanonicalFact, ...],
    effective_time: datetime,
    created_time: datetime,
    instrument: Instrument,
    params: dict[str, object] | None = None,
    registry: StrategyRegistry = DEFAULT_REGISTRY,
) -> Opportunity | None:
    """Evaluate one strategy; return a discovered Opportunity, or None.

    ``indicators`` is a role-keyed mapping (e.g. ``{"short_ma": ..., ...}``
    — each strategy documents which keys it requires). ``facts`` are the
    Canonical Facts backing those indicators, used for evidence and
    ``evidence_confidence`` aggregation (the deterministic minimum across
    contributing facts' own Confidence — the weakest link, per ADR-001's
    "internal reconciliation attribute" framing extended here as a simple,
    documented v1 aggregation choice).

    ``instrument`` is the canonical provider-neutral subject supplied by the
    caller. The Strategy records it unchanged; it performs no symbol parsing,
    lookup, or provider resolution.

    Returns ``None`` when the strategy finds nothing actionable this cycle
    — a legitimate, common outcome; this is a *no-signal* result, not an
    engine failure. No persistence: this ticket does not include an
    Opportunity repository (explicitly out of scope), so no version
    history or "previous opportunity" comparison exists — every discovered
    Opportunity is reported at ``version=1``, ``state=DISCOVERED``, with an
    empty ``guardrail_outcomes`` (guardrails/ranking are later layers).
    """
    require_tz_aware(effective_time, "evaluate_strategy", "effective_time")
    require_tz_aware(created_time, "evaluate_strategy", "created_time")
    params = params or {}

    definition = registry.get(strategy_id)
    signal = definition.compute(indicators, facts, params)
    if signal is None:
        return None

    supporting_indicators = tuple(
        EvidenceReference(
            kind=EvidenceKind.INDICATOR, referenced_id=ind.indicator_id, version=ind.version
        )
        for ind in sorted(signal.contributing_indicators, key=lambda i: i.indicator_id)
    )
    evidence = tuple(
        EvidenceReference(
            kind=EvidenceKind.CANONICAL_FACT, referenced_id=fact.fact_id, version=fact.version
        )
        for fact in sorted(signal.contributing_facts, key=lambda f: f.fact_id)
    )

    evidence_confidence = Confidence(
        score=min(fact.confidence.score for fact in signal.contributing_facts)
    )

    source_indicator_ids = tuple(
        sorted({ind.indicator_id for ind in signal.contributing_indicators})
    )
    source_fact_ids = tuple(sorted({fact.fact_id for fact in signal.contributing_facts}))

    opportunity = Opportunity(
        opportunity_id=opportunity_identity(
            strategy_id,
            instrument,
            source_indicator_ids,
            source_fact_ids,
            effective_time,
            signal.expected_outcome_metrics,
        ),
        version=1,
        strategy_id=strategy_id,
        strategy_version=definition.strategy_version,
        instrument=instrument,
        supporting_indicators=supporting_indicators,
        evidence=evidence,
        assumptions=signal.assumptions,
        evidence_confidence=evidence_confidence,
        expected_outcome_metrics=signal.expected_outcome_metrics,
        state=RecommendationState.DISCOVERED,
        effective_time=effective_time,
        created_time=created_time,
        guardrail_outcomes=(),
    )
    return opportunity
