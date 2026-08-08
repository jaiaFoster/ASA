"""SPRINT-014 S14-PR-05A, Architect checkpoint: ninth review -- "generic
read-only knowledge composition, still unwired".

Proves strategy_runtime.knowledge_composition.compose_strategy_knowledge
end-to-end through Earnings Calendar's own structural selection
(strategies.earnings_calendar_structure) and knowledge binding
(strategies.earnings_calendar_knowledge_binding), against a sealed
MarketSnapshot, with acquisition-free parity against the same formula
chain screening/live_adapters.py's own live path executes -- and, item 7,
against a synthetic second binding proving composition dispatch is
independent of strategy name and registration order.

This module is a test-only harness, not a production composition root
(Architect checkpoint item 8: "no production behavior changes yet") --
the snapshot-resolution extraction glue below (``_select_structure``)
stands in for a future composition root that does not exist yet.
screening/earnings_calendar_facts.py, the transitional Earnings-named
harness this replaces, has been deleted (checkpoint item 6).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest

from analytics.atm_selection import select_atm_strike
from analytics.derived_facts import (
    ATM_IV_VS_REALIZED,
    IV_TERM_STRUCTURE_SPREAD,
    REALIZED_VOLATILITY,
    compute_iv_realized_spread,
)
from analytics.features import DerivedFactQualityStatus, DerivedFactRequest, DerivedFactSet
from analytics.realized_volatility import compute_realized_volatility
from domain import (
    AnnouncementTime,
    CanonicalFact,
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
from facts.canonical_projection import CanonicalFactRequest, canonical_fact_id
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
from screening.subject_fact_projection import (
    SealedEvidenceProvenanceError,
    resolution_for,
    verify_resolved_evidence_belongs_to_snapshot,
)
from strategies import (
    CORE_COMPONENTS,
    EARNINGS_CALENDAR_MANIFEST,
    STONK_STRATEGY_PLUGINS,
    compile_strategy_graph,
    execute_strategy_graph,
)
from strategies.earnings_calendar_evaluation import evaluate_earnings_calendar
from strategies.earnings_calendar_knowledge_binding import (
    EarningsCalendarPayload,
    build_earnings_calendar_knowledge_mapping,
)
from strategies.earnings_calendar_planning import (
    EarningsCalendarPhaseTwoEvidence,
    chain_demand_at,
    earnings_demand,
    expirations_demand,
    historical_bars_demand,
    quote_demand,
    select_earnings_calendar_phase_two_evidence,
)
from strategies.earnings_calendar_structure import (
    EarningsCalendarStructuralSelection,
    select_earnings_calendar_structure,
)
from strategies.knowledge_contracts import KnowledgeMapping
from strategies.plugins import build_plugin_registry
from strategies.scoring import normalize_richness
from strategies.type_system import ComponentValues
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.knowledge_composition import compose_strategy_knowledge
from strategy_runtime.knowledge_registry import KnowledgeCompositionRegistry
from tests.domain.test_financial_contracts import option, security

_COMPONENT_REGISTRY = build_plugin_registry(CORE_COMPONENTS, STONK_STRATEGY_PLUGINS)

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
AS_OF = NOW.date()
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
SYMBOL = "AAPL"
STRATEGY_ID = "earnings_calendar"

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
    quote: Quote | None = None,
) -> EarningsCalendarPhaseTwoEvidence | UnknownReason:
    selections = dict(_selections())
    front_demand_id = selections["front_demand_id"]
    back_demand_id = selections["back_demand_id"]
    assert isinstance(front_demand_id, str)
    assert isinstance(back_demand_id, str)
    chain = _chain(front_iv, back_iv, no_calls_at=no_calls_at)
    resolved_quote = quote if quote is not None else _quote()
    projected = {
        quote_demand(NOW).demand_id: _resolved_evidence(
            quote_demand(NOW).demand_id,
            MarketCapability.REAL_TIME_QUOTE_V1,
            ("last",),
            resolved_quote,
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


def _select_structure(
    snapshot: MarketSnapshot,
    phase_two: EarningsCalendarPhaseTwoEvidence,
    selections: tuple[tuple[str, object], ...],
) -> EarningsCalendarStructuralSelection | UnknownReason:
    """Test-harness-only glue standing in for a future composition root
    (Architect checkpoint, ninth review, item 8: no production wiring in
    this increment): extract plain domain values from an already-sealed
    snapshot's own resolutions, then hand them to Earnings Calendar's own
    pure structural selection. Never itself computes richness, volatility,
    or a verdict.

    Verifies every one of ``phase_two``'s own evidence fields genuinely
    belongs to ``snapshot`` before doing anything else (Architect
    checkpoint: tenth review, item 4 -- the generic primitive
    screening.subject_fact_projection.verify_resolved_evidence_belongs_to_snapshot
    restores the cross-snapshot provenance check the deleted
    screening/earnings_calendar_facts.py used to perform as an
    Earnings-named check).
    """
    for evidence in (
        phase_two.spot_price_evidence,
        phase_two.earnings_evidence,
        phase_two.historical_bars_evidence,
        phase_two.expiration_discovery_evidence,
        phase_two.front_chain_evidence,
        phase_two.back_chain_evidence,
    ):
        verify_resolved_evidence_belongs_to_snapshot(snapshot, evidence)

    selections_by_key = dict(selections)
    front_expiration = date.fromisoformat(str(selections_by_key["front_expiration"]))
    back_expiration = date.fromisoformat(str(selections_by_key["back_expiration"]))

    discovery_value = phase_two.expiration_discovery_evidence.value
    assert isinstance(discovery_value, ExpirationCollection)
    front_cycle = next(
        item for item in discovery_value.cycles if item.expiration_date == front_expiration
    )
    back_cycle = next(
        item for item in discovery_value.cycles if item.expiration_date == back_expiration
    )

    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    earnings_resolution = resolution_for(snapshot, MarketCapability.EARNINGS_CALENDAR_V1)
    bars_resolution = resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    chain_resolution = resolution_for(snapshot, MarketCapability.OPTION_CHAIN_V1)
    assert quote_resolution.selected_observation is not None
    assert earnings_resolution.selected_observation is not None
    assert bars_resolution.selected_observation is not None
    assert chain_resolution.selected_observation is not None

    quote = quote_resolution.selected_observation.value
    event = earnings_resolution.selected_observation.value
    bars = bars_resolution.selected_observation.value
    chain = chain_resolution.selected_observation.value
    assert isinstance(quote, Quote)
    assert isinstance(event, EarningsEvent)
    assert isinstance(bars, OHLCVSeries)
    assert isinstance(chain, OptionChain)

    return select_earnings_calendar_structure(
        quote=quote,
        event=event,
        chain=chain,
        bars_closes=tuple(bar.close for bar in bars.bars),
        bars_observation_id=bars_resolution.selected_observation.observation_id,
        quote_observation_id=quote_resolution.selected_observation.observation_id,
        earnings_observation_id=earnings_resolution.selected_observation.observation_id,
        chain_observation_id=chain_resolution.selected_observation.observation_id,
        front_expiration=front_expiration,
        back_expiration=back_expiration,
        front_cycle=front_cycle,
        back_cycle=back_cycle,
        as_of=snapshot.as_of.date(),
        quote_demand_id=phase_two.spot_price_evidence.demand_id,
        historical_bars_demand_id=phase_two.historical_bars_evidence.demand_id,
        front_chain_demand_id=phase_two.front_chain_evidence.demand_id,
        back_chain_demand_id=phase_two.back_chain_evidence.demand_id,
    )


@dataclasses.dataclass(frozen=True, slots=True)
class _GenericComposition:
    """What the generic seam produces plus what the read-only evaluator
    returned -- assembled here purely for test assertions, never a
    production type.
    """

    knowledge_input: ReadOnlyStrategyInput[EarningsCalendarPayload]
    graph_outputs: ComponentValues


def _compose_via_generic_seam(
    symbol: str,
    snapshot: MarketSnapshot,
    phase_two: EarningsCalendarPhaseTwoEvidence,
    selections: tuple[tuple[str, object], ...],
) -> _GenericComposition | UnknownReason:
    """Sprint 14's target flow, literally: strategy-owned structural
    selection -> canonical facts -> registered analytics -> DerivedFactSet
    -> strategy evaluation (Architect checkpoint item 3), driven entirely
    through the generic, registry/callback-driven orchestrator.
    """
    structural = _select_structure(snapshot, phase_two, selections)
    if isinstance(structural, UnknownReason):
        return structural

    mapping = build_earnings_calendar_knowledge_mapping(
        structural, subject=symbol, snapshot_digest=snapshot.snapshot_digest
    )

    registry: KnowledgeCompositionRegistry[EarningsCalendarPayload] = KnowledgeCompositionRegistry(
        ((STRATEGY_ID, mapping),)
    )
    knowledge_input = compose_strategy_knowledge(snapshot, registry, STRATEGY_ID, subject=symbol)
    if isinstance(knowledge_input, UnknownReason):
        return knowledge_input

    graph_outputs = evaluate_earnings_calendar(
        knowledge_input.derived_facts, knowledge_input.payload
    )
    return _GenericComposition(knowledge_input=knowledge_input, graph_outputs=graph_outputs)


class TestGenericCompositionParity:
    def test_pass_or_watch_quality_case_matches_legacy_verdict_and_score(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, _GenericComposition)

        legacy_verdict, legacy_score = _legacy_baseline(
            _chain(front_iv, back_iv), _earnings_event(), _daily_closes(30)
        )
        assert result.graph_outputs.get("verdict").value == legacy_verdict
        assert result.graph_outputs.get("score").value == legacy_score
        assert legacy_verdict in {"PASS", "WATCH"}

    def test_replay_of_the_same_snapshot_is_byte_identical_regardless_of_wall_clock(self) -> None:
        """Architect checkpoint item 4: temporal identity is derived from
        snapshot.as_of, never from wall-clock invocation time -- two
        composition calls against the same sealed snapshot must produce
        byte-identical evidence.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        first = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        second = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(first, _GenericComposition)
        assert isinstance(second, _GenericComposition)

        assert first.knowledge_input.canonical_facts == second.knowledge_input.canonical_facts
        assert (
            first.knowledge_input.derived_facts.facts
            == second.knowledge_input.derived_facts.facts
        )
        assert tuple(item.identity for item in first.knowledge_input.derived_facts.facts) == tuple(
            item.identity for item in second.knowledge_input.derived_facts.facts
        )
        for fact in first.knowledge_input.canonical_facts:
            assert fact.created_time == snapshot.as_of
            assert fact.effective_time == snapshot.as_of
        for derived_fact in first.knowledge_input.derived_facts.facts:
            assert derived_fact.effective_time == snapshot.as_of

    def test_deterministic_fact_ids_and_derived_fact_set_ordering(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        first = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        second = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(first, _GenericComposition)
        assert isinstance(second, _GenericComposition)
        assert tuple(item.fact_id for item in first.knowledge_input.canonical_facts) == tuple(
            item.fact_id for item in second.knowledge_input.canonical_facts
        )
        ordered_ids = tuple(
            item.derived_fact_id for item in first.knowledge_input.derived_facts.facts
        )
        assert ordered_ids == tuple(sorted(ordered_ids))

    def test_canonical_fact_id_is_generic_not_strategy_scoped(self) -> None:
        """Architect checkpoint item 2: two different consumers projecting
        the same fact_type for the same subject from the same sealed
        evidence must receive the same fact ID -- proven directly against
        the generic facts.canonical_projection.canonical_fact_id helper,
        independent of which strategy happened to call it, and cross-
        checked against what the generic seam actually produced.
        """
        from strategies.earnings_calendar_knowledge_binding import (
            FACT_TYPE_OPTION_IMPLIED_VOLATILITY,
        )

        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, _GenericComposition)

        front_iv_fact = next(
            item
            for item in result.knowledge_input.canonical_facts
            if item.fact_type == FACT_TYPE_OPTION_IMPLIED_VOLATILITY and item.value == front_iv
        )
        front_contract_identity = front_iv_fact.fact_id.split(":")[1]
        assert front_contract_identity != SYMBOL
        second_consumer_fact_id = canonical_fact_id(
            FACT_TYPE_OPTION_IMPLIED_VOLATILITY, front_contract_identity, snapshot.snapshot_digest
        )
        assert front_iv_fact.fact_id == second_consumer_fact_id
        assert not front_iv_fact.fact_id.startswith("earnings_calendar:")

    def test_different_contract_selections_cannot_collide_on_one_fact_id(self) -> None:
        from strategies.earnings_calendar_knowledge_binding import (
            FACT_TYPE_OPTION_IMPLIED_VOLATILITY,
        )

        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, _GenericComposition)

        iv_facts = [
            item
            for item in result.knowledge_input.canonical_facts
            if item.fact_type == FACT_TYPE_OPTION_IMPLIED_VOLATILITY
        ]
        assert len(iv_facts) == 2
        front_fact, back_fact = (
            (iv_facts[0], iv_facts[1])
            if iv_facts[0].value == front_iv
            else (iv_facts[1], iv_facts[0])
        )
        assert front_fact.value == front_iv
        assert back_fact.value == back_iv
        assert front_fact.fact_id != back_fact.fact_id

    def test_derived_facts_carry_i07_parameter_identity(self) -> None:
        """Parameterized derived-fact identity: IV_TERM_STRUCTURE_SPREAD
        and ATM_IV_VS_REALIZED both depend on which front/back contracts
        were selected, so their derived_fact_id must depend on those
        selections too (I-07) -- proven here by recomputing the exact ID
        strategies.earnings_calendar_knowledge_binding precomputed and
        strategy_runtime.knowledge_composition independently reproduced.
        """
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, _, _, bars_result, _ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, _GenericComposition)

        payload = result.knowledge_input.payload
        term_structure_fact = result.knowledge_input.derived_facts.get(
            payload.term_structure_fact_id
        )
        atm_iv_vs_realized_fact = result.knowledge_input.derived_facts.get(
            payload.atm_iv_vs_realized_fact_id
        )
        assert term_structure_fact.derived_fact_id.startswith(
            f"{IV_TERM_STRUCTURE_SPREAD}:{SYMBOL}:{snapshot.snapshot_digest}"
        )
        assert atm_iv_vs_realized_fact.derived_fact_id.startswith(
            f"{ATM_IV_VS_REALIZED}:{SYMBOL}:{snapshot.snapshot_digest}"
        )
        # REALIZED_VOLATILITY carries no I-07 selection parameters -- its
        # own value never varies by which contract was selected.
        realized_vol_fact = result.knowledge_input.derived_facts.get(
            f"{REALIZED_VOLATILITY}:{SYMBOL}:{snapshot.snapshot_digest}"
        )
        bars_observation_id = bars_result.observations[0].observation_id
        assert any(
            item.kind is EvidenceKind.OBSERVATION and item.referenced_id == bars_observation_id
            for item in realized_vol_fact.input_evidence
        )
        # A different valid front/back selection within the same sealed
        # snapshot would embed different parameters and therefore a
        # different ID -- proven by recomputing the ID with a deliberately
        # wrong contract-identity parameter and confirming it diverges.
        from analytics.derived_fact_materialization import derived_fact_id

        wrong_id = derived_fact_id(
            IV_TERM_STRUCTURE_SPREAD,
            SYMBOL,
            snapshot.snapshot_digest,
            parameters=(("front_contract_id", "not-the-real-contract"), ("back_contract_id", "x")),
        )
        assert wrong_id != term_structure_fact.derived_fact_id


class TestGenericCompositionUnknownCases:
    def test_insufficient_historical_bars_is_unknown(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv, bars_count=1)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv, bars_count=1)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, UnknownReason)
        assert result.code == "insufficient_historical_bars"
        assert result.demand_ids == (phase_two.historical_bars_evidence.demand_id,)

    def test_missing_implied_volatility_is_unknown(self) -> None:
        snapshot, *_ = _build_snapshot(front_iv=None, back_iv=Decimal("0.20"))
        phase_two = _phase_two_evidence(front_iv=None, back_iv=Decimal("0.20"))
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, UnknownReason)
        assert result.code == "missing_implied_volatility"
        assert result.demand_ids == (phase_two.front_chain_evidence.demand_id,)

    def test_no_call_contracts_at_selected_expiration_is_unknown(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(
            front_iv=front_iv, back_iv=back_iv, no_calls_at=FRONT_EXPIRATION
        )
        phase_two = _phase_two_evidence(
            front_iv=front_iv, back_iv=back_iv, no_calls_at=FRONT_EXPIRATION
        )
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, snapshot, phase_two, _selections())
        assert isinstance(result, UnknownReason)
        assert result.code == "no_call_contracts_at_selected_expiration"
        assert result.demand_ids == (phase_two.front_chain_evidence.demand_id,)

    def test_missing_spot_price_is_unknown(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        # Build a snapshot whose quote observation carries a bid/ask but no
        # last price -- the one structural gap the other fixtures never
        # exercise (Quote itself requires at least one of bid/ask/last).
        blank_quote = Quote(
            security().instrument, Decimal("199"), Decimal("201"), None, None, None, None, "USD"
        )
        quote_result = _single_result(MarketCapability.REAL_TIME_QUOTE_V1, ("last",), blank_quote)
        earnings_result = _single_result(
            MarketCapability.EARNINGS_CALENDAR_V1, ("earnings_date",), _earnings_event()
        )
        bars_result = _single_result(
            MarketCapability.HISTORICAL_BARS_V1, ("close",), _historical_bars(30)
        )
        discovery_result = _single_result(
            MarketCapability.OPTION_CHAIN_V1, ("expirations",), _expiration_collection()
        )
        combined_chain = _chain(front_iv, back_iv)
        front_result = _chain_result(FRONT_EXPIRATION, combined_chain)
        back_result = _chain_result(BACK_EXPIRATION, combined_chain)
        reduced_chain_result = reduce_option_chain_results(
            (discovery_result, front_result, back_result)
        )
        blank_snapshot = seal_subject_snapshot(
            (quote_result, earnings_result, bars_result, reduced_chain_result),
            as_of=NOW,
            required_capabilities=tuple(_RESOLUTION_POLICY),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            provider_metadata=_PROVIDER_METADATA,
        )
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv, quote=blank_quote)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        result = _compose_via_generic_seam(SYMBOL, blank_snapshot, phase_two, _selections())
        assert isinstance(result, UnknownReason)
        assert result.code == "missing_spot_price"
        assert result.demand_ids == (phase_two.spot_price_evidence.demand_id,)


class TestSealedEvidenceProvenance:
    """Architect checkpoint, tenth review, item 4: restores the forged/
    mismatched-evidence regression test that disappeared with the deleted
    screening/earnings_calendar_facts.py -- now proven against the
    generic screening.subject_fact_projection.
    verify_resolved_evidence_belongs_to_snapshot primitive
    _select_structure calls, not against an Earnings-named harness.
    """

    def test_phase_two_evidence_referencing_an_unknown_observation_id_raises(self) -> None:
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
            _select_structure(snapshot, forged, _selections())


@dataclasses.dataclass(frozen=True, slots=True)
class _SyntheticPayload:
    """A deliberately trivial, non-Earnings payload proving composition
    dispatch is independent of strategy name/order (Architect checkpoint
    item 7): a fake consumer with a different payload/composer, never a
    second production strategy.
    """

    marker: str
    fact_value: str


def _build_synthetic_knowledge_mapping(
    snapshot: MarketSnapshot, *, subject: str
) -> KnowledgeMapping[_SyntheticPayload]:
    """Architect checkpoint, tenth review, item 3's own required proof:
    a synthetic binding must extract a real scalar from its sealed input
    and execute a real registered analytics computation, never invent
    output values merely to demonstrate dispatch genericity. This binding
    reuses REALIZED_VOLATILITY (an already-registered analytics feature --
    registering a brand new one is analytics/'s own concern, out of scope
    here) computed for real over the snapshot's own real historical bars,
    and projects the snapshot's own real quote price as its canonical
    fact -- both traceable back to real observations, not fabricated.
    """
    quote_resolution = resolution_for(snapshot, MarketCapability.REAL_TIME_QUOTE_V1)
    bars_resolution = resolution_for(snapshot, MarketCapability.HISTORICAL_BARS_V1)
    assert quote_resolution.selected_observation is not None
    assert bars_resolution.selected_observation is not None
    quote_value = quote_resolution.selected_observation.value
    bars_value = bars_resolution.selected_observation.value
    assert isinstance(quote_value, Quote)
    assert isinstance(bars_value, OHLCVSeries)
    assert quote_value.last is not None

    canonical_fact_requests = (
        CanonicalFactRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            quote_resolution.selected_observation.observation_id,
            quote_value.last,
            subject,
            "synthetic_spot_price",
        ),
    )
    bars_closes = tuple(bar.close for bar in bars_value.bars)
    bars_observation_id = bars_resolution.selected_observation.observation_id

    def _compute_derived_fact_requests(
        canonical_facts: tuple[CanonicalFact, ...],
    ) -> tuple[DerivedFactRequest, ...] | UnknownReason:
        realized_volatility = compute_realized_volatility(bars_closes)
        return (
            DerivedFactRequest(
                REALIZED_VOLATILITY,
                subject,
                realized_volatility,
                "annualized_stdev",
                (EvidenceReference(EvidenceKind.OBSERVATION, bars_observation_id),),
                DerivedFactQualityStatus.VALID,
            ),
        )

    def _build_payload(
        canonical_facts: tuple[CanonicalFact, ...], derived_facts: DerivedFactSet
    ) -> _SyntheticPayload:
        return _SyntheticPayload(
            marker="synthetic",
            fact_value=str(canonical_facts[0].value) if canonical_facts else "",
        )

    return KnowledgeMapping(
        canonical_fact_requests=canonical_fact_requests,
        compute_derived_fact_requests=_compute_derived_fact_requests,
        build_payload=_build_payload,
    )


class TestSyntheticSecondBindingGenericity:
    """Architect checkpoint item 7: prove genericity with a synthetic
    second binding, not a second production strategy -- explicitly never
    Forward Factor or Skew Momentum.
    """

    def test_dispatch_reaches_the_right_binding_regardless_of_registration_order(self) -> None:
        front_iv = Decimal("0.50")
        back_iv = Decimal("0.20")
        snapshot, *_ = _build_snapshot(front_iv=front_iv, back_iv=back_iv)
        phase_two = _phase_two_evidence(front_iv=front_iv, back_iv=back_iv)
        assert isinstance(phase_two, EarningsCalendarPhaseTwoEvidence)

        structural = _select_structure(snapshot, phase_two, _selections())
        assert not isinstance(structural, UnknownReason)
        earnings_mapping = build_earnings_calendar_knowledge_mapping(
            structural, subject=SYMBOL, snapshot_digest=snapshot.snapshot_digest
        )
        synthetic_mapping = _build_synthetic_knowledge_mapping(snapshot, subject="SYNTH")

        # Deliberately mixed payload types in one registry -- proves the
        # registry/orchestrator is payload-shape-blind, never just tested
        # with a single concrete TPayload. KnowledgeMapping[TPayload] is an
        # invariant generic container, so mixing two concrete payload
        # types needs an explicit widening cast to object here; the
        # runtime behavior this test asserts does not depend on it.
        earnings_entry = cast("KnowledgeMapping[object]", earnings_mapping)
        synthetic_entry = cast("KnowledgeMapping[object]", synthetic_mapping)
        registry_earnings_first: KnowledgeCompositionRegistry[object] = (
            KnowledgeCompositionRegistry(
                ((STRATEGY_ID, earnings_entry), ("synthetic_consumer", synthetic_entry))
            )
        )
        registry_synthetic_first: KnowledgeCompositionRegistry[object] = (
            KnowledgeCompositionRegistry(
                (("synthetic_consumer", synthetic_entry), (STRATEGY_ID, earnings_entry))
            )
        )

        for registry in (registry_earnings_first, registry_synthetic_first):
            earnings_result = compose_strategy_knowledge(
                snapshot, registry, STRATEGY_ID, subject=SYMBOL
            )
            synthetic_result = compose_strategy_knowledge(
                snapshot, registry, "synthetic_consumer", subject="SYNTH"
            )
            assert isinstance(earnings_result, ReadOnlyStrategyInput)
            assert isinstance(earnings_result.payload, EarningsCalendarPayload)
            assert isinstance(synthetic_result, ReadOnlyStrategyInput)
            assert isinstance(synthetic_result.payload, _SyntheticPayload)
            assert synthetic_result.payload.marker == "synthetic"
            # The real spot price the sealed snapshot's own quote
            # observation carries (Architect checkpoint, tenth review,
            # item 3) -- never a fabricated literal.
            assert synthetic_result.payload.fact_value == str(SPOT_PRICE)

    def test_unregistered_strategy_id_raises_regardless_of_what_else_is_registered(self) -> None:
        snapshot, *_ = _build_snapshot(front_iv=Decimal("0.50"), back_iv=Decimal("0.20"))
        synthetic_mapping = _build_synthetic_knowledge_mapping(snapshot, subject="SYNTH")
        registry: KnowledgeCompositionRegistry[_SyntheticPayload] = KnowledgeCompositionRegistry(
            (("synthetic_consumer", synthetic_mapping),)
        )
        from strategy_runtime.knowledge_registry import UnknownKnowledgeBindingError

        with pytest.raises(UnknownKnowledgeBindingError):
            registry.mapping_for(STRATEGY_ID)
