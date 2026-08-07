"""SPRINT-014 S14-PR-05A, Architect checkpoint: read-only Earnings
Calendar fact/analytics composition increment (sixth review's corrective
refactor: strategy-owned evaluation, generic canonical fact identity,
composite ATM_IV_VS_REALIZED, replay-safe temporal identity, immutable
selections, and verified evidence provenance).

Proves screening.earnings_calendar_facts.compose_earnings_calendar_evaluation
end-to-end -- canonical facts, an immutable DerivedFactSet, and the
existing, unmodified Earnings Calendar manifest/graph -- entirely from a
sealed MarketSnapshot, with acquisition-free parity against the same
formula chain screening/live_adapters.py's own live path executes.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from analytics.atm_selection import select_atm_strike
from analytics.derived_facts import (
    ATM_IV_VS_REALIZED,
    IV_TERM_STRUCTURE_SPREAD,
    REALIZED_VOLATILITY,
    compute_iv_realized_spread,
)
from analytics.realized_volatility import compute_realized_volatility
from domain import (
    AnnouncementTime,
    CompletenessMetadata,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    EvidenceUsability,
    ExpirationCollection,
    ExpirationCycle,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    OHLCVBar,
    OHLCVSeries,
    OptionType,
    ProviderProvenance,
    Quote,
    ResolvedCapabilityEvidence,
    UnknownReason,
    market_observation_identity,
)
from domain.financial import OptionChain
from domain.market_data import MarketObservationValue
from facts.canonical_projection import canonical_fact_id
from market_data.capability_coalescing import reduce_option_chain_results
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
from market_data.snapshot import MarketSnapshot
from market_data.subject_snapshot import seal_subject_snapshot
from screening.context_builders import build_earnings_calendar_context
from screening.earnings_calendar_facts import (
    EarningsCalendarComposition,
    SealedEvidenceProvenanceError,
    compose_earnings_calendar_evaluation,
)
from strategies import (
    CORE_COMPONENTS,
    EARNINGS_CALENDAR_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.earnings_calendar_evaluation import FACT_TYPE_FRONT_ATM_IMPLIED_VOLATILITY
from strategies.earnings_calendar_planning import (
    EarningsCalendarPhaseTwoEvidence,
    chain_demand_at,
    earnings_demand,
    expirations_demand,
    historical_bars_demand,
    quote_demand,
    select_earnings_calendar_phase_two_evidence,
)
from strategies.plugins import build_plugin_registry
from strategies.scoring import normalize_richness
from tests.domain.test_financial_contracts import option, security

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
AS_OF = NOW.date()
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
SYMBOL = "AAPL"

# Same policy-valid pair strategies/earnings_calendar_planning's own tests
# use: front 8 DTE (within 7-21), back 43 DTE (within 22-75), 35-day gap
# (within target 30 +/- 5).
EARNINGS_DATE = date(2026, 8, 20)
FRONT_EXPIRATION = date(2026, 8, 14)
BACK_EXPIRATION = date(2026, 9, 18)
SPOT_PRICE = Decimal("200")

_RESOLUTION_POLICY = {
    MarketCapability.REAL_TIME_QUOTE_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("last",)),
    MarketCapability.EARNINGS_CALENDAR_V1: ResolutionPolicy(
        "v1", ("tradier",), 3600, ("earnings_date",)
    ),
    MarketCapability.HISTORICAL_BARS_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("close",)),
    MarketCapability.OPTION_CHAIN_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("contracts",)),
}
_PROVIDER_METADATA = tuple(
    ProviderMetadata(
        ProviderIdentity("tradier", "test_provider", "v1"), (capability,), (), (capability,), "v1"
    )
    for capability in _RESOLUTION_POLICY
)


def _quote() -> Quote:
    return Quote(security().instrument, None, None, SPOT_PRICE, None, None, None, "USD")


def _earnings_event() -> EarningsEvent:
    return EarningsEvent(
        "earnings-1",
        security(),
        EARNINGS_DATE,
        AnnouncementTime.AFTER_CLOSE,
        Decimal("0.05"),
        True,
        (),
        NOW,
        EVIDENCE,
    )


def _bar(day_offset: int, close: Decimal) -> OHLCVBar:
    start = NOW - timedelta(days=day_offset + 1)
    end = start + timedelta(days=1)
    return OHLCVBar(
        security().instrument,
        86400,
        start,
        end,
        close,
        close + Decimal("2"),
        close - Decimal("2"),
        close,
        Decimal("50000000"),
    )


def _daily_closes(count: int) -> tuple[Decimal, ...]:
    # A deliberately volatile alternating series -- annualized realized
    # volatility comfortably below the front IV used below (0.50), giving
    # a positive, non-clamped iv_realized_volatility_richness input.
    closes: list[Decimal] = []
    price = Decimal("195")
    for index in range(count):
        price = price + (Decimal("6") if index % 2 == 0 else Decimal("-5"))
        closes.append(price)
    return tuple(closes)


def _historical_bars(count: int = 30) -> OHLCVSeries:
    closes = _daily_closes(count)
    bars = tuple(_bar(count - 1 - index, close) for index, close in enumerate(closes))
    return OHLCVSeries(security().instrument, 86400, NOW, bars)


def _chain(
    front_iv: Decimal | None, back_iv: Decimal | None, *, no_calls_at: date | None = None
) -> OptionChain:
    underlying = security()
    dates = (FRONT_EXPIRATION, BACK_EXPIRATION)
    contracts = []
    for index, expiration in enumerate(dates):
        option_type = OptionType.PUT if expiration == no_calls_at else OptionType.CALL
        iv = front_iv if expiration == FRONT_EXPIRATION else back_iv
        contract = option(
            expiration=expiration,
            strike=SPOT_PRICE,
            option_type=option_type,
            observed_at=NOW,
            underlying=underlying,
            suffix=f"atm-{expiration.isoformat()}",
        )
        contracts.append(dataclasses.replace(contract, implied_volatility=iv))
        # An off-the-money contract too, so ATM selection genuinely
        # chooses among more than one strike.
        off_strike = option(
            expiration=expiration,
            strike=SPOT_PRICE + Decimal("20"),
            option_type=option_type,
            observed_at=NOW,
            underlying=underlying,
            suffix=f"otm-{expiration.isoformat()}-{index}",
        )
        contracts.append(off_strike)
    return OptionChain("chain-combined", underlying, NOW, tuple(contracts), EVIDENCE)


def _expiration_collection() -> ExpirationCollection:
    cycles = tuple(
        ExpirationCycle(item, (item - AS_OF).days, True, False, AS_OF, EVIDENCE)
        for item in (FRONT_EXPIRATION, BACK_EXPIRATION)
    )
    return ExpirationCollection(AS_OF, cycles)


def _subject(capability: MarketCapability, required_fields: tuple[str, ...]) -> MarketDataSubject:
    subject_type = {
        MarketCapability.OPTION_CHAIN_V1: MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.EARNINGS_CALENDAR_V1: MarketDataSubjectType.EARNINGS_SECURITY,
    }.get(capability, MarketDataSubjectType.INSTRUMENT)
    return MarketDataSubject(
        security().instrument,
        subject_type,
        capability,
        MarketDataRequestContext(NOW, NOW, required_fields, (), EVIDENCE),
    )


def _observation(
    capability: MarketCapability, required_fields: tuple[str, ...], value: MarketObservationValue
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
        ProviderProvenance("tradier", "tradier-request", EVIDENCE),
        FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(required_fields, required_fields, ()),
    )


def _single_result(
    capability: MarketCapability, required_fields: tuple[str, ...], value: MarketObservationValue
) -> CapabilityFulfillmentResult:
    observation = _observation(capability, required_fields, value)
    subject = observation.subject
    request = CapabilityRequest(capability, (subject,), NOW, NOW, required_fields, 3600)
    attempt = ProviderFulfillmentAttempt(
        "tradier", 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    return CapabilityFulfillmentResult(
        request, FulfillmentStatus.FULFILLED, "tradier", (observation,), (attempt,), True
    )


def _chain_result(expiration: date, chain: OptionChain) -> CapabilityFulfillmentResult:
    observation = _observation(MarketCapability.OPTION_CHAIN_V1, ("contracts",), chain)
    subject = observation.subject
    request = CapabilityRequest(
        MarketCapability.OPTION_CHAIN_V1, (subject,), NOW, NOW, ("contracts",), 3600
    )
    attempt = ProviderFulfillmentAttempt(
        "tradier", 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    return CapabilityFulfillmentResult(
        request, FulfillmentStatus.FULFILLED, "tradier", (observation,), (attempt,), True
    )


_SealedSnapshotFixture = tuple[
    MarketSnapshot,
    CapabilityFulfillmentResult,
    CapabilityFulfillmentResult,
    CapabilityFulfillmentResult,
    CapabilityFulfillmentResult,
]


def _build_snapshot(
    *,
    front_iv: Decimal | None,
    back_iv: Decimal | None,
    bars_count: int = 30,
    no_calls_at: date | None = None,
) -> _SealedSnapshotFixture:
    quote_result = _single_result(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), _quote())
    earnings_result = _single_result(
        MarketCapability.EARNINGS_CALENDAR_V1, ("earnings_date",), _earnings_event()
    )
    bars_result = _single_result(
        MarketCapability.HISTORICAL_BARS_V1, ("close",), _historical_bars(bars_count)
    )
    discovery_result = _single_result(
        MarketCapability.OPTION_CHAIN_V1, ("expirations",), _expiration_collection()
    )
    combined_chain = _chain(front_iv, back_iv, no_calls_at=no_calls_at)
    front_result = _chain_result(FRONT_EXPIRATION, combined_chain)
    back_result = _chain_result(BACK_EXPIRATION, combined_chain)
    reduced_chain_result = reduce_option_chain_results(
        (discovery_result, front_result, back_result)
    )

    snapshot = seal_subject_snapshot(
        (quote_result, earnings_result, bars_result, reduced_chain_result),
        as_of=NOW,
        required_capabilities=tuple(_RESOLUTION_POLICY),
        resolution_policy_by_capability=_RESOLUTION_POLICY,
        provider_metadata=_PROVIDER_METADATA,
    )
    return snapshot, quote_result, earnings_result, bars_result, discovery_result


def _selections() -> tuple[tuple[str, object], ...]:
    front = chain_demand_at(NOW, FRONT_EXPIRATION)
    back = chain_demand_at(NOW, BACK_EXPIRATION)
    return (
        ("front_expiration", FRONT_EXPIRATION.isoformat()),
        ("back_expiration", BACK_EXPIRATION.isoformat()),
        ("front_demand_id", front.demand_id),
        ("back_demand_id", back.demand_id),
    )


def _resolved_evidence(
    demand_id: str,
    capability: MarketCapability,
    required_fields: tuple[str, ...],
    value: MarketObservationValue,
) -> ResolvedCapabilityEvidence:
    # Uses the exact same _observation() construction _build_snapshot()'s
    # own _single_result()/_chain_result() helpers use, so the
    # observation_id embedded here is content-identical to what actually
    # lands in the sealed snapshot -- required for
    # _verify_evidence_belongs_to_snapshot's own provenance check to pass
    # against real (not placeholder) observation ids.
    observation_id = _observation(capability, required_fields, value).observation_id
    return ResolvedCapabilityEvidence(
        demand_id,
        capability,
        EvidenceUsability.RESOLVED,
        value,
        (observation_id,),
        FreshnessStatus.FRESH,
    )


def _phase_two_evidence(
    *,
    front_iv: Decimal | None,
    back_iv: Decimal | None,
    bars_count: int = 30,
    no_calls_at: date | None = None,
) -> EarningsCalendarPhaseTwoEvidence | UnknownReason:
    selections = dict(_selections())
    front_demand_id = selections["front_demand_id"]
    back_demand_id = selections["back_demand_id"]
    assert isinstance(front_demand_id, str)
    assert isinstance(back_demand_id, str)
    chain = _chain(front_iv, back_iv, no_calls_at=no_calls_at)
    projected = {
        quote_demand(NOW).demand_id: _resolved_evidence(
            quote_demand(NOW).demand_id, MarketCapability.REAL_TIME_QUOTE_V1, ("last",), _quote()
        ),
        earnings_demand(NOW).demand_id: _resolved_evidence(
            earnings_demand(NOW).demand_id,
            MarketCapability.EARNINGS_CALENDAR_V1,
            ("earnings_date",),
            _earnings_event(),
        ),
        historical_bars_demand(NOW).demand_id: _resolved_evidence(
            historical_bars_demand(NOW).demand_id,
            MarketCapability.HISTORICAL_BARS_V1,
            ("close",),
            _historical_bars(bars_count),
        ),
        expirations_demand(NOW).demand_id: _resolved_evidence(
            expirations_demand(NOW).demand_id,
            MarketCapability.OPTION_CHAIN_V1,
            ("expirations",),
            _expiration_collection(),
        ),
        front_demand_id: _resolved_evidence(
            front_demand_id, MarketCapability.OPTION_CHAIN_V1, ("contracts",), chain
        ),
        back_demand_id: _resolved_evidence(
            back_demand_id, MarketCapability.OPTION_CHAIN_V1, ("contracts",), chain
        ),
    }
    return select_earnings_calendar_phase_two_evidence(projected, selections, now=NOW)


def _legacy_baseline(
    chain: OptionChain, event: EarningsEvent, closes: tuple[Decimal, ...]
) -> tuple[object, object]:
    """The exact formula chain screening/live_adapters.py's own live
    Earnings Calendar path executes -- called here directly on the same
    raw domain data, acquisition-free, for parity comparison.
    """
    front_strikes = tuple(
        item.strike for item in chain.find(expiration=FRONT_EXPIRATION, option_type=OptionType.CALL)
    )
    back_strikes = tuple(
        item.strike for item in chain.find(expiration=BACK_EXPIRATION, option_type=OptionType.CALL)
    )
    front_strike = select_atm_strike(front_strikes, SPOT_PRICE)
    back_strike = select_atm_strike(back_strikes, SPOT_PRICE)
    (front_contract,) = chain.find(
        expiration=FRONT_EXPIRATION, strike=front_strike, option_type=OptionType.CALL
    )
    (back_contract,) = chain.find(
        expiration=BACK_EXPIRATION, strike=back_strike, option_type=OptionType.CALL
    )
    assert front_contract.implied_volatility is not None
    assert back_contract.implied_volatility is not None
    term_richness = normalize_richness(
        front_contract.implied_volatility - back_contract.implied_volatility
    )
    realized_vol = compute_realized_volatility(closes)
    iv_rv_richness = normalize_richness(
        compute_iv_realized_spread(front_contract.implied_volatility, realized_vol)
    )
    front_cycle = ExpirationCycle(
        FRONT_EXPIRATION, (FRONT_EXPIRATION - AS_OF).days, True, False, AS_OF, EVIDENCE
    )
    back_cycle = ExpirationCycle(
        BACK_EXPIRATION, (BACK_EXPIRATION - AS_OF).days, True, False, AS_OF, EVIDENCE
    )
    context = build_earnings_calendar_context(
        chain,
        event,
        front_cycle,
        back_cycle,
        AS_OF,
        target_strike=front_strike,
        term_structure_richness=term_richness,
        iv_realized_volatility_richness=iv_rv_richness,
    )
    graph = compile_strategy_graph(EARNINGS_CALENDAR_MANIFEST, _COMPONENT_REGISTRY)
    result = execute_strategy_graph(graph, context)
    return result.outputs.get("verdict").value, result.outputs.get("score").value


class TestComposeEarningsCalendarEvaluationParity:
    def test_pass_or_watch_quality_case_matches_legacy_verdict_and_score(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, EarningsCalendarComposition)

        legacy_verdict, legacy_score = _legacy_baseline(
            _chain(front_iv, back_iv), _earnings_event(), _daily_closes(30)
        )
        assert result.graph_outputs.get("verdict").value == legacy_verdict
        assert result.graph_outputs.get("score").value == legacy_score
        assert legacy_verdict in {"PASS", "WATCH"}

    def test_replay_of_the_same_snapshot_is_byte_identical_regardless_of_wall_clock(self) -> None:
        """Architect checkpoint item 4: temporal identity is derived from
        snapshot.as_of, never from wall-clock invocation time -- there is
        no wall-clock parameter to vary at all, so two calls (made at
        genuinely different real times, since this test itself runs at
        one real wall-clock moment either way) must produce byte-
        identical evidence.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        first = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        second = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(first, EarningsCalendarComposition)
        assert isinstance(second, EarningsCalendarComposition)

        assert first.canonical_facts == second.canonical_facts
        assert first.derived_facts.facts == second.derived_facts.facts
        assert tuple(item.identity for item in first.derived_facts.facts) == tuple(
            item.identity for item in second.derived_facts.facts
        )
        for fact in first.canonical_facts:
            assert fact.created_time == snapshot.as_of
            assert fact.effective_time == snapshot.as_of
        for derived_fact in first.derived_facts.facts:
            assert derived_fact.effective_time == snapshot.as_of

    def test_deterministic_fact_ids_and_derived_fact_set_ordering(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        first = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        second = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(first, EarningsCalendarComposition)
        assert isinstance(second, EarningsCalendarComposition)
        assert tuple(item.fact_id for item in first.canonical_facts) == tuple(
            item.fact_id for item in second.canonical_facts
        )
        # DerivedFactSet's own deterministic ordering: sorted by
        # derived_fact_id regardless of construction order.
        ordered_ids = tuple(item.derived_fact_id for item in first.derived_facts.facts)
        assert ordered_ids == tuple(sorted(ordered_ids))

    def test_canonical_fact_id_is_generic_not_strategy_scoped(self) -> None:
        """Architect checkpoint item 2: two different "consumers"
        projecting the same fact_type for the same subject from the same
        sealed evidence must receive the same fact ID -- proven directly
        against the generic facts.canonical_projection.canonical_fact_id
        helper, independent of which strategy happened to call it, and
        cross-checked against what compose_earnings_calendar_evaluation
        actually produced.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, EarningsCalendarComposition)

        front_iv_fact = next(
            item
            for item in result.canonical_facts
            if item.fact_type == FACT_TYPE_FRONT_ATM_IMPLIED_VOLATILITY
        )
        # A second, independent "consumer" projecting the identical
        # (fact_type, subject, snapshot_digest) triple -- never told
        # which strategy the first consumer was -- computes the exact
        # same ID.
        second_consumer_fact_id = canonical_fact_id(
            FACT_TYPE_FRONT_ATM_IMPLIED_VOLATILITY, SYMBOL, snapshot.snapshot_digest
        )
        assert front_iv_fact.fact_id == second_consumer_fact_id
        assert not front_iv_fact.fact_id.startswith("earnings_calendar:")

    def test_derived_facts_link_input_evidence_to_what_they_consumed(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, _, _, bars_result, _ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, EarningsCalendarComposition)

        bars_observation_id = bars_result.observations[0].observation_id
        realized_vol_fact = result.derived_facts.get(
            f"{REALIZED_VOLATILITY}:{SYMBOL}:{snapshot.snapshot_digest}"
        )
        assert any(
            item.kind is EvidenceKind.OBSERVATION and item.referenced_id == bars_observation_id
            for item in realized_vol_fact.input_evidence
        )

        front_iv_fact = next(
            item
            for item in result.canonical_facts
            if item.fact_type == "front_atm_implied_volatility"
        )
        back_iv_fact = next(
            item
            for item in result.canonical_facts
            if item.fact_type == "back_atm_implied_volatility"
        )
        term_structure_fact = result.derived_facts.get(
            f"{IV_TERM_STRUCTURE_SPREAD}:{SYMBOL}:{snapshot.snapshot_digest}"
        )
        referenced_fact_ids = {
            item.referenced_id
            for item in term_structure_fact.input_evidence
            if item.kind is EvidenceKind.CANONICAL_FACT
        }
        assert referenced_fact_ids == {front_iv_fact.fact_id, back_iv_fact.fact_id}

        iv_rv_fact = result.derived_facts.get(
            f"{ATM_IV_VS_REALIZED}:{SYMBOL}:{snapshot.snapshot_digest}"
        )
        iv_rv_referenced = {item.referenced_id for item in iv_rv_fact.input_evidence}
        # ATM_IV_VS_REALIZED is a composite feature owning its own
        # realized-volatility computation -- its input_evidence never
        # references the separately-materialized REALIZED_VOLATILITY
        # DerivedFact (EvidenceKind has no derived-fact reference kind),
        # only the canonical front IV and the raw bars observation.
        assert front_iv_fact.fact_id in iv_rv_referenced
        assert bars_observation_id in iv_rv_referenced
        assert realized_vol_fact.derived_fact_id not in iv_rv_referenced


class TestComposeEarningsCalendarEvaluationUnknownCases:
    def test_insufficient_historical_bars_is_unknown(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv, bars_count=1)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv, bars_count=1)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, UnknownReason)
        assert result.code == "insufficient_historical_bars"

    def test_missing_implied_volatility_is_unknown(self) -> None:
        snapshot, *_ = _build_snapshot(front_iv=None, back_iv=Decimal("0.20"))
        phase_two = _phase_two_evidence(front_iv=None, back_iv=Decimal("0.20"))
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, UnknownReason)
        assert result.code == "missing_implied_volatility"

    def test_no_call_contracts_at_selected_expiration_is_unknown(self) -> None:
        """Architect checkpoint item 6: select_atm_strike()'s own empty-
        strike-set ValueError must never escape raw -- a resolved chain
        that simply lists no CALL contracts at the selected front
        expiration is a genuine, typed data gap.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(
            front_iv=front_iv, back_iv=back_iv, no_calls_at=FRONT_EXPIRATION
        )
        phase_two = _phase_two_evidence(
            front_iv=front_iv, back_iv=back_iv, no_calls_at=FRONT_EXPIRATION
        )
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = compose_earnings_calendar_evaluation(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, UnknownReason)
        assert result.code == "no_call_contracts_at_selected_expiration"


class TestSealedEvidenceProvenance:
    def test_phase_two_evidence_referencing_an_unknown_observation_id_raises(self) -> None:
        """Architect checkpoint item 6: a mismatched evidence bundle is
        an invariant/provenance failure, never ordinary UNKNOWN.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        forged = dataclasses.replace(
            phase_two,
            historical_bars_evidence=dataclasses.replace(
                phase_two.historical_bars_evidence, observation_ids=("not-in-the-snapshot",)
            ),
        )

        with pytest.raises(SealedEvidenceProvenanceError):
            compose_earnings_calendar_evaluation(SYMBOL, snapshot, forged, _selections())
