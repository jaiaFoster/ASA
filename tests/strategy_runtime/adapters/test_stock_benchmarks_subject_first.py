"""STOCK-RUNTIME-001 STK-03: proves B001/B002's own preparation callbacks
(``_prepare_b001``/``_prepare_b002``), the generic
``compose_strategy_knowledge`` orchestrator, and the subject-first runtime
adapters actually produce the frozen benchmark semantics
(project/reports/STOCK-RUNTIME-001-STK-01.md):

- B001: usable quote -> PASS/BUY; unusable quote -> typed UnknownReason
  (surfaced generically as MISSING_DATA, never reached by the adapter).
- B002: price above SMA10M -> PASS/BUY; at or below -> NO_SIGNAL; fewer
  than ten completed months of adjusted-close history -> typed
  UnknownReason, never a raw-close fallback.
- Deterministic replay: composing the same sealed snapshot twice produces
  byte-identical facts, proving SMA10M is computed from sealed evidence,
  never a fresh provider call.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from domain import (
    AdjustedCloseBasis,
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    OHLCVBar,
    OHLCVSeries,
    ProviderProvenance,
    Quote,
    UnknownReason,
    market_observation_identity,
)
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    FulfillmentStatus,
    ProviderFulfillmentAttempt,
)
from market_data.providers import (
    CapabilityRequest,
    ProviderIdentity,
    ProviderMetadata,
    ProviderStatus,
)
from market_data.resolution import ResolutionPolicy
from market_data.subject_snapshot import seal_subject_snapshot
from strategy_runtime.adapters.stock_benchmarks import B001_CONTRACT, B002_CONTRACT
from strategy_runtime.adapters.stock_benchmarks_subject_first import (
    _prepare_b001,
    _prepare_b002,
    build_b001_subject_first_adapter,
    build_b002_subject_first_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.knowledge_composition import compose_strategy_knowledge
from strategy_runtime.knowledge_registry import KnowledgeCompositionRegistry
from strategy_runtime.result import EvaluationState
from tests.domain.test_financial_contracts import security

NOW = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)
SYMBOL = "SPY"
_INSTRUMENT = security(SYMBOL).instrument
_EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:SPY"),)
_RESOLUTION_POLICY = {
    MarketCapability.REAL_TIME_QUOTE_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("last",)),
    MarketCapability.HISTORICAL_BARS_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("close",)),
}
_PROVIDER_METADATA = tuple(
    ProviderMetadata(
        ProviderIdentity("tradier", "test_provider", "v1"), (capability,), (), (capability,), "v1"
    )
    for capability in _RESOLUTION_POLICY
)


def _quote(price: Decimal | None) -> Quote:
    if price is None:
        # Quote requires at least one of bid/ask/last -- an "unusable"
        # quote for these benchmarks (which only ever read .last) is one
        # with a bid/ask but no last trade, not an impossible all-None
        # quote the domain model itself refuses to construct.
        return Quote(_INSTRUMENT, Decimal("1"), Decimal("2"), None, None, None, None, "USD")
    return Quote(_INSTRUMENT, None, None, price, None, None, None, "USD")


def _month_end_bar(months_back: int, *, adjusted_close: Decimal | None) -> OHLCVBar:
    total_months = NOW.year * 12 + (NOW.month - 1) - months_back
    year, month = divmod(total_months, 12)
    end_at = datetime(year, month + 1, 15, 12, 0, tzinfo=UTC)
    start_at = end_at - timedelta(days=1)
    close = Decimal("400") + Decimal(months_back)
    basis = AdjustedCloseBasis.SPLIT_ADJUSTED if adjusted_close is not None else None
    return OHLCVBar(
        _INSTRUMENT,
        86400,
        start_at,
        end_at,
        close,
        close + Decimal("2"),
        close - Decimal("2"),
        close,
        Decimal("1000000"),
        adjusted_close,
        basis,
    )


def _ten_completed_months(*, price_above_sma: bool) -> tuple[OHLCVBar, ...]:
    # Ascending adjusted closes 401..410 -> mean (SMA10M) == 405.5.
    return tuple(
        _month_end_bar(months_back, adjusted_close=Decimal("400") + months_back)
        for months_back in range(1, 11)
    )


def _subject(capability: MarketCapability, required_fields: tuple[str, ...]) -> MarketDataSubject:
    return MarketDataSubject(
        _INSTRUMENT,
        MarketDataSubjectType.INSTRUMENT,
        capability,
        MarketDataRequestContext(NOW, NOW, required_fields, (), _EVIDENCE),
    )


def _observation(
    capability: MarketCapability, required_fields: tuple[str, ...], value: object
) -> MarketObservation:
    subject = _subject(capability, required_fields)
    identity = market_observation_identity("tradier", capability, subject, NOW, value, "v1")
    return MarketObservation(
        identity,
        capability,
        subject,
        NOW,
        NOW,
        value,
        "v1",
        ProviderProvenance("tradier", "tradier-request", _EVIDENCE),
        FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(required_fields, required_fields, ()),
    )


def _single_result(
    capability: MarketCapability, required_fields: tuple[str, ...], value: object
) -> CapabilityFulfillmentResult:
    observation = _observation(capability, required_fields, value)
    request = CapabilityRequest(capability, (observation.subject,), NOW, NOW, required_fields, 3600)
    attempt = ProviderFulfillmentAttempt(
        "tradier", 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    return CapabilityFulfillmentResult(
        request, FulfillmentStatus.FULFILLED, "tradier", (observation,), (attempt,), True
    )


def _b001_snapshot(*, price: Decimal | None):
    quote_result = _single_result(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), _quote(price))
    return seal_subject_snapshot(
        (quote_result,),
        as_of=NOW,
        required_capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,),
        resolution_policy_by_capability=_RESOLUTION_POLICY,
        provider_metadata=(_PROVIDER_METADATA[0],),
    )


def _b002_snapshot(*, price: Decimal | None, bars: tuple[OHLCVBar, ...]):
    quote_result = _single_result(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), _quote(price))
    bars_result = _single_result(
        MarketCapability.HISTORICAL_BARS_V1,
        ("close",),
        OHLCVSeries(_INSTRUMENT, 86400, NOW, bars),
    )
    return seal_subject_snapshot(
        (quote_result, bars_result),
        as_of=NOW,
        required_capabilities=(
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketCapability.HISTORICAL_BARS_V1,
        ),
        resolution_policy_by_capability=_RESOLUTION_POLICY,
        provider_metadata=_PROVIDER_METADATA,
    )


class TestB001PrepareAndAdapter:
    def test_usable_quote_produces_pass_and_buy(self) -> None:
        snapshot = _b001_snapshot(price=Decimal("560.25"))
        mapping = _prepare_b001(snapshot, {}, (), SYMBOL)
        assert not isinstance(mapping, UnknownReason)

        registry = KnowledgeCompositionRegistry((("B001", mapping),))
        knowledge = compose_strategy_knowledge(snapshot, registry, "B001", subject=SYMBOL)
        assert not isinstance(knowledge, UnknownReason)

        adapter = build_b001_subject_first_adapter({SYMBOL: knowledge})
        context = RuntimeContext(
            contract=B001_CONTRACT, subject=SYMBOL, clock=_Clock(), run_id="run-1"
        )
        result = adapter(context)

        assert result.verdict == "PASS"
        assert result.evaluation_state is EvaluationState.PASS
        assert result.opportunity_id is None
        assert result.lifecycle_stage is None
        assert result.metrics["price"].native() == Decimal("560.25")
        assert result.metrics["direction"].native() == "BUY"

    def test_unusable_quote_is_a_typed_unknown_not_a_fabricated_result(self) -> None:
        snapshot = _b001_snapshot(price=None)
        mapping = _prepare_b001(snapshot, {}, (), SYMBOL)
        assert isinstance(mapping, UnknownReason)
        assert mapping.code == "unusable_quote"


class TestB002PrepareAndAdapter:
    def _knowledge(self, *, price: Decimal, bars: tuple[OHLCVBar, ...]):
        snapshot = _b002_snapshot(price=price, bars=bars)
        mapping = _prepare_b002(snapshot, {}, (), SYMBOL)
        assert not isinstance(mapping, UnknownReason)
        registry = KnowledgeCompositionRegistry((("B002", mapping),))
        knowledge = compose_strategy_knowledge(snapshot, registry, "B002", subject=SYMBOL)
        return snapshot, knowledge

    def test_price_above_sma_is_pass_and_buy(self) -> None:
        bars = _ten_completed_months(price_above_sma=True)
        _snapshot, knowledge = self._knowledge(price=Decimal("450"), bars=bars)
        assert not isinstance(knowledge, UnknownReason)

        adapter = build_b002_subject_first_adapter({SYMBOL: knowledge})
        context = RuntimeContext(
            contract=B002_CONTRACT, subject=SYMBOL, clock=_Clock(), run_id="run-1"
        )
        result = adapter(context)

        assert result.verdict == "PASS"
        assert result.evaluation_state is EvaluationState.PASS
        assert result.metrics["sma_10m_completed_months"].native() == Decimal("405.5")
        assert result.metrics["direction"].native() == "BUY"

    def test_price_at_or_below_sma_is_no_signal_without_direction(self) -> None:
        bars = _ten_completed_months(price_above_sma=False)
        _snapshot, knowledge = self._knowledge(price=Decimal("405.5"), bars=bars)
        assert not isinstance(knowledge, UnknownReason)

        adapter = build_b002_subject_first_adapter({SYMBOL: knowledge})
        context = RuntimeContext(
            contract=B002_CONTRACT, subject=SYMBOL, clock=_Clock(), run_id="run-1"
        )
        result = adapter(context)

        assert result.verdict == "NO_SIGNAL"
        assert result.evaluation_state is EvaluationState.NO_SIGNAL
        assert "direction" not in result.metrics

    def test_insufficient_adjusted_history_is_a_typed_unknown_never_a_raw_close_fallback(
        self,
    ) -> None:
        nine_months = tuple(
            _month_end_bar(months_back, adjusted_close=Decimal("400") + months_back)
            for months_back in range(1, 10)
        )
        snapshot = _b002_snapshot(price=Decimal("450"), bars=nine_months)
        mapping = _prepare_b002(snapshot, {}, (), SYMBOL)
        assert not isinstance(mapping, UnknownReason)

        registry = KnowledgeCompositionRegistry((("B002", mapping),))
        result = compose_strategy_knowledge(snapshot, registry, "B002", subject=SYMBOL)

        assert isinstance(result, UnknownReason)
        assert result.code == "insufficient_adjusted_history"

    def test_unusable_quote_is_a_typed_unknown(self) -> None:
        bars = _ten_completed_months(price_above_sma=True)
        snapshot = _b002_snapshot(price=None, bars=bars)
        mapping = _prepare_b002(snapshot, {}, (), SYMBOL)
        assert isinstance(mapping, UnknownReason)
        assert mapping.code == "unusable_quote"

    def test_replay_from_the_same_sealed_snapshot_is_deterministic(self) -> None:
        bars = _ten_completed_months(price_above_sma=True)
        snapshot, first = self._knowledge(price=Decimal("450"), bars=bars)
        mapping = _prepare_b002(snapshot, {}, (), SYMBOL)
        assert not isinstance(mapping, UnknownReason)
        registry = KnowledgeCompositionRegistry((("B002", mapping),))
        second = compose_strategy_knowledge(snapshot, registry, "B002", subject=SYMBOL)

        assert not isinstance(first, UnknownReason)
        assert not isinstance(second, UnknownReason)
        assert first.payload == second.payload
        assert (
            first.derived_facts.facts[0].derived_fact_id
            == second.derived_facts.facts[0].derived_fact_id
        )
        assert first.derived_facts.facts[0].value == second.derived_facts.facts[0].value


class _Clock:
    def now(self) -> datetime:
        return NOW
