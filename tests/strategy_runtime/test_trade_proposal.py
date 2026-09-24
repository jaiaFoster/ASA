from __future__ import annotations

from dataclasses import replace
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
from strategy_runtime.option_payoff import (
    DeterministicTerminalPayoff,
    PayoffQuantity,
    PayoffQuantityState,
    TerminalPayoffPoint,
    same_strike_calendar_loss_bound,
)
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.trade_proposal import (
    LiquidityState,
    OptionTradeProposal,
    QuantityState,
    TradeProposalUnavailable,
    build_option_trade_proposal,
    classify_trade_blocker,
    trade_proposal_to_data,
)
from strategy_runtime.values import TypedValue
from tests.strategy_runtime.test_option_payoff import _vertical

NOW = datetime(2026, 9, 23, 16, tzinfo=UTC)
FRONT = date(2026, 10, 16)
BACK = date(2026, 11, 20)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "chain-observation", 1),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("symbol", "AAPL"), InstrumentKind.EQUITY, "AAPL", "USD"
)
SECURITY = Security(INSTRUMENT, "AAPL", SecurityAssetType.EQUITY, "NASDAQ")


def _contract(expiration: date, bid: str, ask: str) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"AAPL-{expiration}-200-C"),
        SECURITY,
        expiration,
        Decimal("200"),
        OptionType.CALL,
        Decimal(bid),
        Decimal(ask),
        (Decimal(bid) + Decimal(ask)) / 2,
        25,
        100,
        Decimal("0.50"),
        None,
        None,
        None,
        None,
        Decimal("0.30"),
        NOW,
        EVIDENCE,
    )


def _assessment(*, compatible: bool = True):  # type: ignore[no-untyped-def]
    back_strike = Decimal("200") if compatible else Decimal("205")
    chain_contracts = (
        _contract(FRONT, "2.00", "2.20"),
        _contract(BACK, "4.00", "4.40"),
    )
    intent = OptionStructureIntent(
        "AAPL",
        StructureKind.CALENDAR,
        (
            OptionLegIntent(
                "short_front",
                OptionType.CALL,
                FRONT,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_strike=Decimal("200"),
            ),
            OptionLegIntent(
                "long_back",
                OptionType.CALL,
                BACK,
                OptionLegPosition.LONG,
                Decimal(1),
                selected_strike=back_strike,
            ),
        ),
    )
    return resolve_option_structure(
        intent=intent,
        chain=OptionChain("chain-1", SECURITY, NOW, chain_contracts, EVIDENCE),
        originating_result_identity="result-1",
        evidence_snapshot_identity="snapshot-1",
        assessed_at=NOW,
    )


def _result(observation_id: str = "result-1") -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id="earnings_calendar",
        strategy_version="1.2.0",
        symbol="AAPL",
        observation_id=observation_id,
        opportunity_id="opportunity-1",
        row_type=RowType.RESULT,
        verdict="PASS",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage="confirmed",
        recommendation_state=None,
        data_quality="complete",
        metrics={"gate.liquidity_acceptable": TypedValue.of_boolean(True)},
        economics={},
        blockers=(),
        warnings=("monitor earnings timing",),
        provenance=("snapshot_id:snapshot-1",),
        observed_at=NOW,
    )


def test_constructible_calendar_projects_exact_trade_with_only_its_loss_bound() -> None:
    assessment = _assessment()

    proposal = build_option_trade_proposal(_result(), assessment)

    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.underlying == "AAPL"
    assert proposal.strategy_id == "earnings_calendar"
    assert proposal.structure == "calendar"
    assert [leg.buy_or_sell for leg in proposal.legs] == ["sell", "buy"]
    assert [leg.expiration for leg in proposal.legs] == [FRONT, BACK]
    assert proposal.modeled_net_debit_or_credit == Decimal("2.10")
    assert proposal.liquidity is LiquidityState.ACCEPTABLE
    assert proposal.legs[0].actual_delta == Decimal("0.50")
    # Same-strike debit calendar: loss is bounded by the modeled debit, while
    # profit and breakeven depend on the later leg's model value.
    assert proposal.maximum_loss.state is QuantityState.SUPPORTED
    assert proposal.maximum_loss.value == Decimal("210.00")
    assert proposal.capital_required.value == Decimal("210.00")
    assert proposal.maximum_profit.state is QuantityState.UNKNOWN
    assert proposal.maximum_profit.reason == "later_expiring_leg_value_is_model_dependent"
    assert proposal.breakeven.state is QuantityState.UNKNOWN
    assert "maximum_loss_model:same-strike-calendar-debit-bound-v1" in proposal.assumptions
    assert {
        "maximum_loss_assumption:long_leg_exercisable_american_style",
        "maximum_loss_assumption:long_leg_exercised_or_closed_promptly_on_assignment",
        "maximum_loss_assumption:excludes_dividend_owed_after_early_call_assignment",
    } <= set(proposal.assumptions)
    assert any("ex-dividend" in note for note in proposal.risk_notes)
    assert proposal.invalidation_notes == ("not_defined_by_strategy",)
    assert "modeled entry is not an executed fill" in proposal.risk_notes
    assert len(proposal.identity) == 64
    data = trade_proposal_to_data(proposal)
    assert data["proposal_identity"] == proposal.identity
    assert data["modeled_entry"]["semantics"] == "modeled_reference_only"  # type: ignore[index]


def test_nonconstructible_assessment_stays_typed_unavailable() -> None:
    unavailable = build_option_trade_proposal(_result(), _assessment(compatible=False))

    assert isinstance(unavailable, TradeProposalUnavailable)
    assert unavailable.constructibility == "not_constructible"
    assert unavailable.reason_code == "no_compatible_contract"
    assert unavailable.blocker_category == "contract_selection"
    assert "compatible option contract" in unavailable.user_message
    assert trade_proposal_to_data(unavailable)["status"] == "unavailable"


def test_assessment_identity_must_match_result() -> None:
    with pytest.raises(ValueError, match="does not belong"):
        build_option_trade_proposal(_result("different-result"), _assessment())


def test_attached_terminal_payoff_populates_only_supported_quantities() -> None:
    assessment = _assessment()
    payoff = DeterministicTerminalPayoff(
        structure_assessment_identity=assessment.identity,
        model_version="exact-leg-terminal-payoff-v1",
        expiration=FRONT,
        points=(TerminalPayoffPoint(Decimal("200"), Decimal("0")),),
        contract_multiplier=Decimal("100"),
        entry_fill_assumption="midpoint_modeled_reference_only",
        maximum_loss=PayoffQuantity(PayoffQuantityState.SUPPORTED, Decimal("210")),
        maximum_profit=PayoffQuantity(PayoffQuantityState.UNDEFINED, None, "not_supported"),
        breakevens=(Decimal("202.10"),),
    )

    proposal = build_option_trade_proposal(_result(), assessment, payoff)

    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.maximum_loss.value == Decimal("210")
    assert proposal.maximum_profit.state is QuantityState.UNDEFINED
    assert proposal.breakeven.value == Decimal("202.10")


@pytest.mark.parametrize(
    ("reason", "category"),
    (
        ("stale_option_chain", "stale_evidence"),
        ("earnings_clearance:unknown", "earnings_uncertainty"),
        ("liquidity_gate_failed", "liquidity"),
        ("missing_implied_volatility", "missing_volatility"),
        ("missing_actual_delta", "missing_delta"),
        ("no_valid_expiration_pair", "expiration"),
        ("no_compatible_contract", "contract_selection"),
        ("modeled_midpoint_entry_unavailable", "missing_quote"),
        ("unsupported_structure", "unsupported_structure"),
    ),
)
def test_failure_categories_preserve_common_typed_blockers(reason: str, category: str) -> None:
    classified, message = classify_trade_blocker(reason)

    assert classified == category
    assert message


def test_same_expiration_structure_derives_deterministic_bounds_without_attachment() -> None:
    assessment = replace(_vertical(), originating_result_identity="result-1")

    proposal = build_option_trade_proposal(_result(), assessment)

    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.maximum_loss.value == Decimal("400.00")
    assert proposal.maximum_profit.value == Decimal("600.00")
    assert proposal.breakeven.value == Decimal("104")
    assert proposal.capital_required.value == Decimal("400.00")
    assert "payoff_model:exact-leg-terminal-payoff-v1" in proposal.assumptions


def test_same_strike_calendar_loss_bound_applies_only_to_that_exact_shape() -> None:
    bound = same_strike_calendar_loss_bound(_assessment())

    assert bound == PayoffQuantity(PayoffQuantityState.SUPPORTED, Decimal("210.00"))
    assert same_strike_calendar_loss_bound(_assessment(), Decimal("10")) == PayoffQuantity(
        PayoffQuantityState.SUPPORTED, Decimal("21.00")
    )
    # Same-expiration legs, unresolved structures, and credit entries get no bound.
    assert same_strike_calendar_loss_bound(_vertical()) is None
    assert same_strike_calendar_loss_bound(_assessment(compatible=False)) is None
    credit = _assessment()
    assert credit.modeled_entry_economics is not None
    credit = replace(
        credit,
        modeled_entry_economics=replace(
            credit.modeled_entry_economics, modeled_net_debit_or_credit=Decimal("-0.10")
        ),
    )
    assert same_strike_calendar_loss_bound(credit) is None


def _shape(  # type: ignore[no-untyped-def]
    *,
    types=(OptionType.CALL, OptionType.CALL),
    strikes=("200", "200"),
    expirations=(FRONT, BACK),
    quantities=("1", "1"),
    debit="2.10",
):
    """Duck-typed short/long pair isolating the bound's shape guard."""
    from types import SimpleNamespace

    from strategy_runtime.executable_structures import ExecutableStructureStatus

    legs = tuple(
        SimpleNamespace(
            leg=SimpleNamespace(
                position=position,
                quantity=Decimal(quantity),
                contract=SimpleNamespace(
                    option_type=option_type, strike=Decimal(strike), expiration=expiration
                ),
            )
        )
        for position, option_type, strike, expiration, quantity in zip(
            (OptionLegPosition.SHORT, OptionLegPosition.LONG),
            types,
            strikes,
            expirations,
            quantities,
            strict=True,
        )
    )
    return SimpleNamespace(
        status=ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED,
        modeled_entry_economics=SimpleNamespace(modeled_net_debit_or_credit=Decimal(debit)),
        exact_legs=legs,
    )


@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        ({}, Decimal("210.00")),
        ({"types": (OptionType.PUT, OptionType.PUT)}, Decimal("210.00")),
        ({"quantities": ("3", "3"), "debit": "6.30"}, Decimal("630.00")),
        ({"expirations": (BACK, FRONT)}, None),
        ({"expirations": (FRONT, FRONT)}, None),
        ({"quantities": ("1", "2")}, None),
        ({"strikes": ("200", "205")}, None),
        ({"types": (OptionType.CALL, OptionType.PUT)}, None),
        ({"debit": "0"}, None),
    ],
)
def test_calendar_bound_shape_guard(shape: dict[str, object], expected: Decimal | None) -> None:
    bound = same_strike_calendar_loss_bound(_shape(**shape))  # type: ignore[arg-type]

    assert (None if bound is None else bound.value) == expected


def test_projected_bounds_do_not_depend_on_display_grid() -> None:
    from strategy_runtime.option_payoff import model_terminal_payoff

    assessment = replace(_vertical(), originating_result_identity="result-1")
    sparse = model_terminal_payoff(
        assessment=assessment, underlying_price_grid=(Decimal("1"), Decimal("500"))
    )
    assert isinstance(sparse, DeterministicTerminalPayoff)

    derived = build_option_trade_proposal(_result(), assessment)
    attached = build_option_trade_proposal(_result(), assessment, sparse)

    assert isinstance(derived, OptionTradeProposal)
    assert isinstance(attached, OptionTradeProposal)
    for field in ("maximum_loss", "maximum_profit", "breakeven", "capital_required"):
        assert getattr(derived, field) == getattr(attached, field)
