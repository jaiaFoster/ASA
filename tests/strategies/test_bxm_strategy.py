from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    MarketCapability,
    OptionChain,
    OptionContract,
    OptionType,
    Security,
    SecurityAssetType,
    SettlementStyle,
    UnknownReason,
)
from strategies.bxm_evaluation import NO_ACTION, evaluate_bxm
from strategies.bxm_knowledge import BxmPayload
from strategies.bxm_manifest import BXM_MANIFEST, STRATEGY_ID
from strategies.bxm_planning import bootstrap_demands, resolved_field_requirements
from strategies.manifest import ParameterSpec
from strategies.tristate_components import PASS, UNKNOWN
from strategy_runtime.adapters.bxm import BXM_CONTRACT
from strategy_runtime.adapters.bxm_subject_first import build_bxm_overlay
from strategy_runtime.contract import StructureKind

ROLL = datetime(2026, 10, 16, 14, 55, tzinfo=UTC)
EXPIRY = date(2026, 11, 20)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "spx-chain", 1),)
SPX = Security(
    Instrument(
        CanonicalInstrumentIdentity("index_root", "SPX"), InstrumentKind.INDEX, "SPX", "USD"
    ),
    "SPX",
    SecurityAssetType.INDEX,
    "CBOE",
)


def _call(
    strike: str, *, root: str = "SPX", settlement: SettlementStyle = SettlementStyle.AM
) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"SPX-{EXPIRY}-{strike}-C"),
        SPX,
        EXPIRY,
        Decimal(strike),
        OptionType.CALL,
        Decimal("50"),
        Decimal("51"),
        None,
        10,
        10,
        Decimal("0.5"),
        None,
        None,
        None,
        None,
        None,
        ROLL,
        EVIDENCE,
        root,
        settlement,
    )


def _chain(*contracts: OptionContract) -> OptionChain:
    return OptionChain("spx-chain", SPX, ROLL, contracts, EVIDENCE)


def test_bxm_manifest_contract_and_capabilities_are_production_exact() -> None:
    assert BXM_CONTRACT.strategy_id == STRATEGY_ID
    assert BXM_CONTRACT.structure is StructureKind.CUSTOM
    assert {item.name for item in BXM_MANIFEST.required_market_capabilities} >= {
        "option_trade_tape_v1",
        "index_dividend_points_v1",
        "index_settlement_value_v1",
    }


def test_bxm_selects_closest_standard_next_month_call_at_or_above_reference() -> None:
    chain = _chain(
        _call("4995"),
        _call("5000"),
        _call("5005"),
        _call("5001", root="SPXW", settlement=SettlementStyle.PM),
    )
    decision = evaluate_bxm(
        decision_date=ROLL.date(),
        roll_date=ROLL.date(),
        quote_effective_time=ROLL,
        quote_value=Decimal("5002"),
        chain=chain,
    )
    assert decision.verdict == PASS
    assert decision.selected_call is not None
    assert decision.selected_call.strike == Decimal("5005")
    payload = BxmPayload(
        chain,
        Decimal("5002"),
        ROLL,
        UnknownReason("OPTION_TRADE_TAPE_UNAVAILABLE"),
        None,
        UnknownReason("INDEX_DIVIDEND_POINTS_UNAVAILABLE"),
        UnknownReason("INDEX_SETTLEMENT_VALUE_UNAVAILABLE"),
    )
    overlay = build_bxm_overlay(payload, decision)
    assert overlay.broker_executable is False
    assert overlay.underlying.instrument.display_symbol == "SPX"
    assert overlay.option_legs[0].contract.identity == decision.selected_call.identity


def test_manifest_parameters_are_the_live_selection_and_quantity_authority() -> None:
    nodes = []
    for node in BXM_MANIFEST.nodes:
        if node.node_id == "selection":
            values = {item.name: item for item in node.parameters}
            values["contract_root"] = ParameterSpec("contract_root", "Text", "SPXW")
            values["settlement_style"] = ParameterSpec("settlement_style", "Text", "pm")
            node = replace(node, parameters=tuple(values.values()))
        elif node.node_id == "short_call_quantity":
            node = replace(
                node, parameters=(ParameterSpec("value", "Decimal", "2"),)
            )
        nodes.append(node)
    changed = replace(BXM_MANIFEST, nodes=tuple(nodes), strategy_version="1.0.1")
    decision = evaluate_bxm(
        decision_date=ROLL.date(),
        roll_date=ROLL.date(),
        quote_effective_time=ROLL,
        quote_value=Decimal("5000"),
        chain=_chain(
            _call("5000"),
            _call("5001", root="SPXW", settlement=SettlementStyle.PM),
        ),
        manifest=changed,
    )
    assert decision.verdict == PASS
    assert decision.selected_call is not None
    assert decision.selected_call.root == "SPXW"
    assert decision.short_call_quantity == Decimal(2)


def test_bxm_truth_table_and_wrong_contract_identity_fail_closed() -> None:
    assert (
        evaluate_bxm(
            decision_date=date(2026, 10, 12),
            roll_date=ROLL.date(),
            quote_effective_time=ROLL,
            quote_value=Decimal("5000"),
            chain=_chain(_call("5000")),
        ).verdict
        == NO_ACTION
    )
    assert (
        evaluate_bxm(
            decision_date=ROLL.date(),
            roll_date=UnknownReason("calendar_unavailable"),
            quote_effective_time=ROLL,
            quote_value=Decimal("5000"),
            chain=_chain(_call("5000")),
        ).verdict
        == UNKNOWN
    )
    result = evaluate_bxm(
        decision_date=ROLL.date(),
        roll_date=ROLL.date(),
        quote_effective_time=ROLL,
        quote_value=Decimal("5000"),
        chain=_chain(_call("5000", root="SPXW", settlement=SettlementStyle.PM)),
    )
    assert result.verdict == UNKNOWN
    assert result.reason == "G_BXM_STRIKE_EXISTS_UNKNOWN"


def test_bxm_plans_every_declared_lifecycle_capability_as_optional_where_appropriate() -> None:
    now = datetime(2026, 10, 16, 15, 0, tzinfo=UTC)
    demands = bootstrap_demands(now)
    by_capability = {item.capability: item for item in demands}
    for capability in (
        MarketCapability.OPTION_TRADE_TAPE_V1,
        MarketCapability.INDEX_DIVIDEND_POINTS_V1,
        MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
    ):
        assert by_capability[capability].required is False
        assert capability in resolved_field_requirements()
    tape = by_capability[MarketCapability.OPTION_TRADE_TAPE_V1]
    start_utc = tape.effective_start.astimezone(UTC)
    end_utc = tape.effective_end.astimezone(UTC)
    assert (start_utc.hour, start_utc.minute) == (15, 30)
    assert (end_utc.hour, end_utc.minute) == (17, 30)
