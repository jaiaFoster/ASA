"""P03 generic straddle (STRATEGY-PRODUCTION-001 SP-02A).

Long and short, unit and non-unit ratios, multi-pair collections, exact
contract and quantity identity, deterministic ordering, and the generic trade
proposal projection. Two different consumers (a long zero-delta event
straddle and a short index-style straddle) use the same primitive.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionLegPosition,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import ExecutableStructureStatus
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.trade_proposal import (
    OptionTradeProposal,
    QuantityState,
    build_option_trade_proposal,
    trade_proposal_to_data,
)

NOW = datetime(2026, 9, 28, 20, tzinfo=UTC)
EXPIRY = date(2026, 10, 9)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "chain-observation", 1),)
SECURITY = Security(
    Instrument(CanonicalInstrumentIdentity("symbol", "AAPL"), InstrumentKind.EQUITY, "AAPL", "USD"),
    "AAPL",
    SecurityAssetType.EQUITY,
    "NASDAQ",
)


def _contract(
    strike: str, option_type: OptionType, bid: str, ask: str, delta: str
) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"AAPL-{EXPIRY}-{strike}-{option_type.value}"),
        SECURITY,
        EXPIRY,
        Decimal(strike),
        option_type,
        Decimal(bid),
        Decimal(ask),
        None,
        10,
        100,
        Decimal(delta),
        None,
        None,
        None,
        None,
        None,
        NOW,
        EVIDENCE,
    )


CHAIN = OptionChain(
    "chain-1",
    SECURITY,
    NOW,
    (
        _contract("200", OptionType.CALL, "5.00", "5.20", "0.52"),
        _contract("200", OptionType.PUT, "4.80", "5.00", "-0.48"),
        _contract("205", OptionType.CALL, "2.90", "3.10", "0.40"),
        _contract("205", OptionType.PUT, "7.70", "7.90", "-0.60"),
    ),
    EVIDENCE,
)


def _pair(
    strike: str, position: OptionLegPosition, call_qty: str, put_qty: str
) -> tuple[OptionLegIntent, OptionLegIntent]:
    return (
        OptionLegIntent(
            f"{strike}.call",
            OptionType.CALL,
            EXPIRY,
            position,
            Decimal(call_qty),
            selected_strike=Decimal(strike),
        ),
        OptionLegIntent(
            f"{strike}.put",
            OptionType.PUT,
            EXPIRY,
            position,
            Decimal(put_qty),
            selected_strike=Decimal(strike),
        ),
    )


def _resolve(*legs: OptionLegIntent):  # type: ignore[no-untyped-def]
    return resolve_option_structure(
        intent=OptionStructureIntent("AAPL", StructureKind.STRADDLE, legs),
        chain=CHAIN,
        originating_result_identity="result-1",
        evidence_snapshot_identity="snapshot-1",
        assessed_at=NOW,
    )


def _result() -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id="p03_fixture",
        strategy_version="1.0.0",
        symbol="AAPL",
        observation_id="result-1",
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict="PASS",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=("snapshot_id:snapshot-1",),
        observed_at=NOW,
    )


def test_long_unit_straddle_is_constructible_and_projects_exact_legs() -> None:
    assessment = _resolve(*_pair("200", OptionLegPosition.LONG, "1", "1"))
    assert assessment.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    assert assessment.available_structure_kind is StructureKind.STRADDLE
    assert assessment.modeled_entry_economics is not None
    assert assessment.modeled_entry_economics.modeled_net_debit_or_credit == Decimal("10.00")
    proposal = build_option_trade_proposal(_result(), assessment)
    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.structure == "straddle"
    assert [(leg.call_or_put, leg.buy_or_sell) for leg in proposal.legs] == [
        ("call", "buy"),
        ("put", "buy"),
    ]
    # Long straddle: loss bounded by the debit; profit unbounded above.
    assert proposal.maximum_loss.state is QuantityState.SUPPORTED
    assert proposal.maximum_loss.value == Decimal("1000.00")
    assert proposal.maximum_profit.state is not QuantityState.SUPPORTED
    assert trade_proposal_to_data(proposal)["structure"] == "straddle"


def test_non_unit_zero_delta_ratio_is_exact_quantity_identity() -> None:
    unit = _resolve(*_pair("200", OptionLegPosition.LONG, "1", "1"))
    ratio = _resolve(*_pair("200", OptionLegPosition.LONG, "0.48", "0.52"))
    assert ratio.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    assert [item.leg.quantity for item in ratio.exact_legs] == [Decimal("0.48"), Decimal("0.52")]
    assert ratio.identity != unit.identity


def test_multi_pair_collection_without_a_strategy_specific_type() -> None:
    assessment = _resolve(
        *_pair("205", OptionLegPosition.LONG, "1", "1"),
        *_pair("200", OptionLegPosition.LONG, "2", "2"),
    )
    assert assessment.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    assert [item.leg.contract.strike for item in assessment.exact_legs] == [
        Decimal("200"),
        Decimal("200"),
        Decimal("205"),
        Decimal("205"),
    ]


def test_ordering_is_deterministic_regardless_of_intent_order() -> None:
    a = _resolve(
        *_pair("200", OptionLegPosition.LONG, "1", "1"),
        *_pair("205", OptionLegPosition.LONG, "1", "1"),
    )
    call, put = _pair("205", OptionLegPosition.LONG, "1", "1")
    other_call, other_put = _pair("200", OptionLegPosition.LONG, "1", "1")
    b = _resolve(put, other_call, call, other_put)
    assert a.identity == b.identity


def test_short_straddle_second_consumer_reuses_the_primitive() -> None:
    assessment = _resolve(*_pair("200", OptionLegPosition.SHORT, "1", "1"))
    assert assessment.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    proposal = build_option_trade_proposal(_result(), assessment)
    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.modeled_net_debit_or_credit == Decimal("-10.00")
    assert [leg.buy_or_sell for leg in proposal.legs] == ["sell", "sell"]
    # Short straddle loss is unbounded: never a supported finite number.
    assert proposal.maximum_loss.state is not QuantityState.SUPPORTED


def test_mixed_direction_or_mismatched_strikes_is_not_a_straddle() -> None:
    call, _ = _pair("200", OptionLegPosition.LONG, "1", "1")
    _, put = _pair("200", OptionLegPosition.SHORT, "1", "1")
    mixed = _resolve(call, put)
    assert mixed.status is ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE
    call_200, _ = _pair("200", OptionLegPosition.LONG, "1", "1")
    _, put_205 = _pair("205", OptionLegPosition.LONG, "1", "1")
    strangle = _resolve(call_200, put_205)
    assert strangle.status is ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE
    assert strangle.available_structure_kind is StructureKind.CUSTOM


def test_duplicate_contract_and_odd_leg_counts_are_rejected() -> None:
    call, put = _pair("200", OptionLegPosition.LONG, "1", "1")
    with pytest.raises(ValueError):
        OptionStructureIntent("AAPL", StructureKind.STRADDLE, (call,))
    dup_call = OptionLegIntent(
        "dup.call",
        OptionType.CALL,
        EXPIRY,
        OptionLegPosition.LONG,
        Decimal(1),
        selected_strike=Decimal("200"),
    )
    dup_put = OptionLegIntent(
        "dup.put",
        OptionType.PUT,
        EXPIRY,
        OptionLegPosition.LONG,
        Decimal(1),
        selected_strike=Decimal("200"),
    )
    duplicate = _resolve(call, put, dup_call, dup_put)
    assert duplicate.status is ExecutableStructureStatus.NOT_CONSTRUCTIBLE
    assert duplicate.reason_code == "duplicate_contract_in_structure"


def test_existing_two_leg_structures_are_unchanged() -> None:
    call, put = _pair("200", OptionLegPosition.LONG, "1", "1")
    with pytest.raises(ValueError):
        OptionStructureIntent("AAPL", StructureKind.VERTICAL, (call, put, call))
