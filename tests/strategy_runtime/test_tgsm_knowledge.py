"""S001 sealed historical-evidence binding regression vectors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from analytics.derived_fact_materialization import materialize_derived_fact
from analytics.derived_facts import DERIVED_FACT_REGISTRY
from analytics.features import DerivedFactSet
from domain import (
    AdjustedCloseBasis,
    CanonicalFact,
    Confidence,
    MarketCapability,
    OHLCVBar,
    OHLCVSeries,
    Provenance,
    UnknownReason,
)
from market_data.subject_snapshot import seal_subject_snapshot
from strategies.tgsm_knowledge import build_s001_knowledge_mapping
from strategy_runtime.adapters.tgsm_subject_first import _prepare_s001
from strategy_runtime.knowledge_composition import compose_strategy_knowledge
from strategy_runtime.knowledge_registry import KnowledgeCompositionRegistry
from tests.domain.test_financial_contracts import security
from tests.strategy_runtime.adapters.test_stock_benchmarks_subject_first import (
    _INSTRUMENT,
    _PROVIDER_METADATA,
    _RESOLUTION_POLICY,
    _single_result,
)

NOW = datetime(2026, 9, 5, 15, tzinfo=UTC)


def _history(basis: AdjustedCloseBasis) -> tuple[OHLCVBar, ...]:
    bars = []
    for months_back in range(13, 0, -1):
        month_index = NOW.year * 12 + NOW.month - 1 - months_back
        year, month_zero = divmod(month_index, 12)
        end = datetime(year, month_zero + 1, 25, tzinfo=UTC)
        price = Decimal(113 - months_back)
        bars.append(
            OHLCVBar(
                security("SPY").instrument,
                86400,
                end - timedelta(days=1),
                end,
                price,
                price,
                price,
                price,
                Decimal(1000),
                price,
                basis,
            )
        )
    return tuple(bars)


def _canonical(request, snapshot_digest: str) -> CanonicalFact:
    from facts.canonical_projection import canonical_fact_id

    return CanonicalFact(
        canonical_fact_id(request.fact_type, request.subject, snapshot_digest),
        1,
        request.fact_type,
        request.value,
        Confidence(1.0),
        Provenance(("observation",), ("fixture",), "fixture", (), NOW),
        NOW,
        NOW,
    )


def test_s001_materializes_both_named_facts_from_total_return_history() -> None:
    mapping = build_s001_knowledge_mapping(
        subject="XLE",
        snapshot_digest="digest",
        bars_observation_id="observation",
        bars=_history(AdjustedCloseBasis.SPLIT_AND_DIVIDEND_ADJUSTED),
        as_of=NOW,
    )
    assert not isinstance(mapping, UnknownReason)
    facts = tuple(_canonical(item, "digest") for item in mapping.canonical_fact_requests)
    requests = mapping.compute_derived_fact_requests(facts)
    assert not isinstance(requests, UnknownReason)
    assert {item.feature_id for item in requests} == {
        "trailing_12m_total_return",
        "sma_10m_completed_months",
    }
    derived = DerivedFactSet(
        tuple(
            materialize_derived_fact(
                DERIVED_FACT_REGISTRY,
                request.feature_id,
                request.subject,
                "digest",
                value=request.value,
                unit=request.unit,
                effective_time=NOW,
                input_evidence=request.input_evidence,
                quality_status=request.quality_status,
            )
            for request in requests
        )
    )
    payload = mapping.build_payload(facts, derived)
    assert payload.trailing_return == Decimal("0.12")
    assert payload.trend_observation == Decimal("112")
    assert payload.sma_10m is not None
    assert payload.trailing_return_fact_id in {item.derived_fact_id for item in derived.facts}


def test_s001_generic_composer_projects_sealed_bars_before_derived_facts() -> None:
    bars = _history(AdjustedCloseBasis.SPLIT_AND_DIVIDEND_ADJUSTED)
    result = _single_result(
        MarketCapability.HISTORICAL_BARS_V1,
        ("close",),
        OHLCVSeries(_INSTRUMENT, 86400, NOW, bars),
    )
    snapshot = seal_subject_snapshot(
        (result,),
        as_of=NOW,
        required_capabilities=(MarketCapability.HISTORICAL_BARS_V1,),
        resolution_policy_by_capability=_RESOLUTION_POLICY,
        provider_metadata=(_PROVIDER_METADATA[1],),
    )
    mapping = _prepare_s001(snapshot, {}, (), "SPY")
    assert not isinstance(mapping, UnknownReason)
    registry = KnowledgeCompositionRegistry((("S001", mapping),))
    first = compose_strategy_knowledge(snapshot, registry, "S001", subject="SPY")
    second = compose_strategy_knowledge(snapshot, registry, "S001", subject="SPY")
    assert first == second
    assert not isinstance(first, UnknownReason)
    assert len(first.canonical_facts) == 2
    assert len(first.derived_facts.facts) == 2


def test_s001_rejects_split_only_evidence() -> None:
    mapping = build_s001_knowledge_mapping(
        subject="XLE",
        snapshot_digest="digest",
        bars_observation_id="observation",
        bars=_history(AdjustedCloseBasis.SPLIT_ADJUSTED),
        as_of=NOW,
    )
    assert not isinstance(mapping, UnknownReason)
    facts = tuple(_canonical(item, "digest") for item in mapping.canonical_fact_requests)
    assert mapping.compute_derived_fact_requests(facts) == UnknownReason(
        "unusable_total_return_history"
    )


def test_s001_incomplete_history_is_typed_unknown() -> None:
    result = build_s001_knowledge_mapping(
        subject="XLE",
        snapshot_digest="digest",
        bars_observation_id="observation",
        bars=_history(AdjustedCloseBasis.SPLIT_AND_DIVIDEND_ADJUSTED)[:12],
        as_of=NOW,
    )
    assert result == UnknownReason("insufficient_total_return_history")
