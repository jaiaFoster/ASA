from datetime import UTC, date, datetime
from decimal import Decimal

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
from strategies.scs_evaluation import NO_ACTION, PASS, UNKNOWN, evaluate_scs
from strategies.scs_manifest import SCS_MANIFEST, STRATEGY_ID
from strategies.scs_planning import expand_demands, expirations_demand
from strategy_runtime.adapters.scs import SCS_CONTRACT
from strategy_runtime.adapters.scs_subject_first import build_scs_structure_intent
from strategy_runtime.contract import StructureKind

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
        CanonicalInstrumentIdentity("occ", f"SPX-{EXPIRY}-{strike}-{side}"),
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
