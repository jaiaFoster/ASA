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
    trade_proposal_to_data,
)
from strategy_runtime.values import TypedValue

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


def test_constructible_assessment_projects_exact_trade_without_invented_payoff() -> None:
    assessment = _assessment()

    proposal = build_option_trade_proposal(_result(), assessment)

    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.underlying == "AAPL"
    assert proposal.strategy_id == "earnings_calendar"
    assert proposal.structure == "calendar"
    assert [leg.buy_or_sell for leg in proposal.legs] == ["short", "long"]
    assert [leg.expiration for leg in proposal.legs] == [FRONT, BACK]
    assert proposal.modeled_net_debit_or_credit == Decimal("2.10")
    assert proposal.liquidity is LiquidityState.ACCEPTABLE
    assert proposal.legs[0].actual_delta == Decimal("0.50")
    assert proposal.maximum_loss.state is QuantityState.UNKNOWN
    assert proposal.maximum_loss.value is None
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
    assert trade_proposal_to_data(unavailable)["status"] == "unavailable"


def test_assessment_identity_must_match_result() -> None:
    with pytest.raises(ValueError, match="does not belong"):
        build_option_trade_proposal(_result("different-result"), _assessment())
