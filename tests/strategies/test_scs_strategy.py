from datetime import UTC, date, datetime
from decimal import Decimal

from analytics.features import DerivedFactSet
from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    EvidenceUsability,
    ExpirationCollection,
    ExpirationCycle,
    FreshnessStatus,
    Instrument,
    InstrumentKind,
    MarketCapability,
    OptionChain,
    OptionContract,
    OptionLegPosition,
    OptionType,
    ResolvedCapabilityEvidence,
    Security,
    SecurityAssetType,
    SettlementStyle,
)
from strategies.scs_evaluation import NO_ACTION, evaluate_scs
from strategies.scs_knowledge import SCSPayload
from strategies.scs_manifest import SCS_MANIFEST, STRATEGY_ID
from strategies.scs_planning import bootstrap_demands, expand_demands, expirations_demand
from strategies.tristate_components import PASS, UNKNOWN
from strategy_runtime.adapters.scs import SCS_CONTRACT
from strategy_runtime.adapters.scs_subject_first import (
    build_scs_structure_intent,
    build_scs_subject_first_adapter,
)
from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import StructureKind
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.persistence import LifecyclePositionState
from strategy_runtime.result import EvaluationState

NOW = datetime(2026, 10, 1, 15, tzinfo=UTC)
EXPIRY = date(2026, 11, 20)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "scs-chain", 1),)
SPX = Security(
    Instrument(
        CanonicalInstrumentIdentity("index_root", "SPX"), InstrumentKind.INDEX, "SPX", "USD"
    ),
    "SPX",
    SecurityAssetType.INDEX,
    "CBOE",
)


def _option(
    strike: str,
    option_type: OptionType,
    *,
    root: str = "SPX",
    settlement: SettlementStyle = SettlementStyle.AM,
) -> OptionContract:
    side = "C" if option_type is OptionType.CALL else "P"
    return OptionContract(
        CanonicalInstrumentIdentity(
            "occ", f"{root}-{settlement.value}-{EXPIRY}-{strike}-{side}"
        ),
        SPX,
        EXPIRY,
        Decimal(strike),
        option_type,
        Decimal("99.90"),
        Decimal("100.10"),
        None,
        10,
        10,
        Decimal("0.5") if option_type is OptionType.CALL else Decimal("-0.5"),
        None,
        None,
        None,
        None,
        Decimal("0.20"),
        NOW,
        EVIDENCE,
        root,
        settlement,
    )


def _chain(*contracts: OptionContract) -> OptionChain:
    return OptionChain("scs-chain", SPX, NOW, contracts, EVIDENCE)


def _resolved_expirations(*cycles: ExpirationCycle) -> ResolvedCapabilityEvidence:
    demand = expirations_demand(NOW)
    collection = ExpirationCollection(NOW.date(), cycles)
    return ResolvedCapabilityEvidence(
        demand.demand_id,
        MarketCapability.OPTION_CHAIN_V1,
        EvidenceUsability.RESOLVED,
        collection,
        ("scs-expirations",),
        FreshnessStatus.FRESH,
    )


def test_contract_manifest_and_assumption_are_frozen() -> None:
    assert SCS_CONTRACT.strategy_id == STRATEGY_ID
    assert SCS_CONTRACT.structure is StructureKind.STRADDLE
    assert {item.assumption_id for item in SCS_MANIFEST.assumptions} == {"RA-SV-01"}
    assert MarketCapability.TRADING_CALENDAR_V1 not in {
        MarketCapability(item.name) for item in SCS_MANIFEST.required_market_capabilities
    }


def test_named_rate_series_are_distinct_provider_neutral_demands() -> None:
    rates = tuple(
        demand
        for demand in bootstrap_demands(NOW)
        if demand.capability is MarketCapability.RATE_OBSERVATION_V1
    )
    assert {item.subject_symbol for item in rates} == {
        "US_TBILL_4WK_BANK_DISCOUNT",
        "SP500_DIVIDEND_YIELD",
    }
    assert len({item.demand_id for item in rates}) == 2


def test_unique_monthly_expiration_closest_to_45_days_is_selected() -> None:
    cycles = (
        ExpirationCycle(date(2026, 11, 13), 43, False, True, NOW.date(), EVIDENCE),
        ExpirationCycle(date(2026, 11, 20), 50, True, False, NOW.date(), EVIDENCE),
        ExpirationCycle(date(2026, 11, 13), 43, True, False, NOW.date(), EVIDENCE),
    )
    result = expand_demands(
        {expirations_demand(NOW).demand_id: _resolved_expirations(*cycles)}, now=NOW
    )
    assert result.selections == (("expiration", "2026-11-13"),)
    assert result.demands[0].expiration == date(2026, 11, 13)


def test_equal_distance_monthlies_are_ambiguous() -> None:
    cycles = (
        ExpirationCycle(date(2026, 11, 10), 40, True, False, NOW.date(), EVIDENCE),
        ExpirationCycle(date(2026, 11, 20), 50, True, False, NOW.date(), EVIDENCE),
    )
    result = expand_demands(
        {expirations_demand(NOW).demand_id: _resolved_expirations(*cycles)}, now=NOW
    )
    assert tuple(item.code for item in result.unknown_reasons) == ("AMBIGUOUS_SELECTION",)


def test_non_entry_date_is_no_action_before_market_evidence() -> None:
    decision = evaluate_scs(
        decision_date=NOW.date(),
        entry_date_state="FAIL",
        selected_expiration=EXPIRY,
        spot=None,
        chain=None,
        rate=None,
        dividend_yield=None,
    )
    assert decision.verdict == NO_ACTION


def test_missing_rate_or_dividend_yield_is_typed_unknown() -> None:
    chain = _chain(_option("5000", OptionType.CALL), _option("5000", OptionType.PUT))
    decision = evaluate_scs(
        decision_date=NOW.date(),
        entry_date_state=PASS,
        selected_expiration=EXPIRY,
        spot=Decimal("5000"),
        chain=chain,
        rate=None,
        dividend_yield=Decimal("0.01"),
    )
    assert decision.verdict == UNKNOWN
    assert decision.reason == "G_SCS_QUOTE_FILTERS_UNKNOWN"


def test_passing_pair_projects_exact_two_short_contracts() -> None:
    chain = _chain(_option("5000", OptionType.CALL), _option("5000", OptionType.PUT))
    decision = evaluate_scs(
        decision_date=NOW.date(),
        entry_date_state=PASS,
        selected_expiration=EXPIRY,
        spot=Decimal("5000"),
        chain=chain,
        rate=Decimal("0.04"),
        dividend_yield=Decimal("0.01"),
    )
    assert decision.verdict == PASS
    intent = build_scs_structure_intent("SPX", decision)
    assert tuple(item.position for item in intent.legs) == (
        OptionLegPosition.SHORT,
        OptionLegPosition.SHORT,
    )
    assert tuple(item.quantity for item in intent.legs) == (Decimal(1), Decimal(1))
    assert {item.selected_contract_identity for item in intent.legs} == {
        contract.identity for contract in chain.contracts
    }
    assert decision.call_naked_margin == Decimal("850.000")
    assert decision.put_naked_margin == Decimal("850.000")
    assert decision.straddle_margin == Decimal("950.000")


def test_mixed_root_and_settlement_panel_selects_only_exact_manifest_pair() -> None:
    chain = _chain(
        _option("5000", OptionType.CALL, root="AAA", settlement=SettlementStyle.PM),
        _option("5000", OptionType.PUT, root="AAA", settlement=SettlementStyle.PM),
        _option("5000", OptionType.CALL),
        _option("5000", OptionType.PUT),
    )
    decision = evaluate_scs(
        decision_date=NOW.date(),
        entry_date_state=PASS,
        selected_expiration=EXPIRY,
        spot=Decimal("5000"),
        chain=chain,
        rate=Decimal("0.04"),
        dividend_yield=Decimal("0.01"),
    )
    assert decision.verdict == PASS
    assert decision.selected_call is not None and decision.selected_call.root == "SPX"
    assert decision.selected_put is not None and decision.selected_put.root == "SPX"
    assert decision.selected_call.settlement_style is SettlementStyle.AM
    assert decision.selected_put.settlement_style is SettlementStyle.AM


def test_equal_distance_atm_strikes_never_choose_arbitrarily() -> None:
    chain = _chain(
        _option("4995", OptionType.CALL),
        _option("4995", OptionType.PUT),
        _option("5005", OptionType.CALL),
        _option("5005", OptionType.PUT),
    )
    decision = evaluate_scs(
        decision_date=NOW.date(),
        entry_date_state=PASS,
        selected_expiration=EXPIRY,
        spot=Decimal("5000"),
        chain=chain,
        rate=Decimal("0.04"),
        dividend_yield=Decimal("0.01"),
    )
    assert decision.verdict == UNKNOWN
    assert decision.reason == "AMBIGUOUS_SELECTION"


def test_persisted_position_holds_then_reforms_at_next_month_close() -> None:
    class Clock:
        def __init__(self, value: datetime) -> None:
            self.value = value

        def now(self) -> datetime:
            return self.value

    chain = _chain(_option("5000", OptionType.CALL), _option("5000", OptionType.PUT))
    knowledge = ReadOnlyStrategyInput(
        "snapshot",
        "digest",
        NOW,
        (),
        DerivedFactSet(()),
        SCSPayload(
            chain,
            Decimal("5000"),
            EXPIRY,
            Decimal("0.04"),
            Decimal("0.01"),
            datetime(2026, 11, 2, 21, 5, tzinfo=UTC),
            None,
        ),
    )
    prior = LifecyclePositionState("old-call|old-put", date(2026, 10, 1), date(2026, 12, 18))
    hold_at = datetime(2026, 10, 15, 20, 5, tzinfo=UTC)
    hold = build_scs_subject_first_adapter({"SPX": knowledge}, {"SPX": prior})(
        RuntimeContext(SCS_CONTRACT, "SPX", Clock(hold_at), "hold")
    )
    assert hold.verdict == "HOLD"
    assert hold.lifecycle_stage == "entered"
    assert hold.metrics["lifecycle.held_position_identity"].native() == prior.position_identity

    reform_at = datetime(2026, 11, 2, 21, 5, tzinfo=UTC)
    reform = build_scs_subject_first_adapter({"SPX": knowledge}, {"SPX": prior})(
        RuntimeContext(SCS_CONTRACT, "SPX", Clock(reform_at), "reform")
    )
    assert reform.evaluation_state is EvaluationState.PASS
    assert reform.lifecycle_stage == "entered"
    assert reform.metrics["lifecycle.exited_position_identity"].native() == prior.position_identity
    assert reform.metrics["lifecycle.held_position_identity"].native() != prior.position_identity
    assert reform.economics["margin.call.formula"].native() == (
        "DF-CBOE-NAKED-MARGIN@1.1.0"
    )
    assert reform.economics["margin.straddle.formula"].native() == (
        "DF-CBOE-STRADDLE-MARGIN@1.0.0"
    )
    assert reform.economics["margin.straddle"].native() == Decimal("950")

    latest_policy = build_scs_subject_first_adapter(
        {"SPX": knowledge},
        {"SPX": prior},
        exit_policy="latest_candidate_date",
    )(RuntimeContext(SCS_CONTRACT, "SPX", Clock(reform_at), "latest-policy"))
    assert latest_policy.verdict == "HOLD"
    assert latest_policy.metrics["lifecycle.held_position_identity"].native() == (
        prior.position_identity
    )


def test_expiry_before_next_entry_requires_matching_settlement() -> None:
    class Clock:
        def now(self) -> datetime:
            return datetime(2026, 10, 16, 21, tzinfo=UTC)

    chain = _chain(_option("5000", OptionType.CALL), _option("5000", OptionType.PUT))
    knowledge = ReadOnlyStrategyInput(
        "snapshot",
        "digest",
        NOW,
        (),
        DerivedFactSet(()),
        SCSPayload(
            chain,
            Decimal("5000"),
            EXPIRY,
            Decimal("0.04"),
            Decimal("0.01"),
            NOW,
            None,
        ),
    )
    prior = LifecyclePositionState("old-call|old-put", date(2026, 10, 1), date(2026, 10, 16))
    result = build_scs_subject_first_adapter({"SPX": knowledge}, {"SPX": prior})(
        RuntimeContext(SCS_CONTRACT, "SPX", Clock(), "expiry")
    )
    assert result.evaluation_state is EvaluationState.MISSING_DATA
    assert result.lifecycle_stage == "expired"
    assert result.blockers == ("SCS_EXPIRY_SETTLEMENT_UNKNOWN",)
