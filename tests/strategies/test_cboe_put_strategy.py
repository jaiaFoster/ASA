from datetime import UTC, date, datetime
from decimal import Decimal

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionType,
    Quote,
    Security,
    SecurityAssetType,
    SettlementStyle,
)
from strategies.cboe_put_evaluation import NO_ACTION, PASS, UNKNOWN, evaluate_cboe_put
from strategies.cboe_put_manifest import CBOE_PUT_MANIFEST, STRATEGY_ID
from strategies.cboe_put_planning import _next_month_expiration
from strategy_runtime.adapters.cboe_put import CBOE_PUT_CONTRACT
from strategy_runtime.adapters.cboe_put_subject_first import _spot, build_cboe_put_structure_intent
from strategy_runtime.contract import StructureKind
from strategy_runtime.option_structure_resolver import resolve_option_structure
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.trade_proposal import OptionTradeProposal, build_option_trade_proposal

ROLL = datetime(2026, 10, 16, 14, 55, tzinfo=UTC)  # 10:55 ET
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


def _put(
    strike: str, *, root: str = "SPX", settlement: SettlementStyle = SettlementStyle.AM
) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"SPX-{EXPIRY}-{strike}-P"),
        SPX,
        EXPIRY,
        Decimal(strike),
        OptionType.PUT,
        Decimal("50"),
        Decimal("51"),
        None,
        10,
        10,
        Decimal("-0.5"),
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


def test_contract_and_manifest_are_exact_and_provider_blind() -> None:
    assert CBOE_PUT_CONTRACT.strategy_id == STRATEGY_ID
    assert CBOE_PUT_CONTRACT.structure is StructureKind.SINGLE_LEG
    assert {item.assumption_id for item in CBOE_PUT_MANIFEST.assumptions} == {"IA-PUT-01"}


def test_roll_selects_highest_standard_am_spx_put_not_above_reference() -> None:
    decision = evaluate_cboe_put(
        decision_date=ROLL.date(),
        roll_date=ROLL.date(),
        reference_state=PASS,
        quote_value=Decimal("5002"),
        chain=_chain(
            _put("4995"),
            _put("5000"),
            _put("5005"),
            _put("5001", root="SPXW", settlement=SettlementStyle.PM),
        ),
    )
    assert decision.verdict == PASS
    assert decision.selected_put is not None
    assert decision.selected_put.strike == Decimal("5000")

    result = UniversalScreeningResult(
        STRATEGY_ID,
        CBOE_PUT_CONTRACT.version,
        "SPX",
        "put-result",
        "put-opportunity",
        RowType.RESULT,
        PASS,
        EvaluationState.PASS,
        "identified",
        None,
        None,
        {},
        {},
        (),
        (),
        ("snapshot_id:snapshot-1",),
        ROLL,
    )
    assessment = resolve_option_structure(
        intent=build_cboe_put_structure_intent("SPX", decision),
        chain=_chain(_put("4995"), _put("5000"), _put("5005")),
        originating_result_identity=result.observation_id,
        evidence_snapshot_identity="snapshot-1",
        assessed_at=ROLL,
    )
    proposal = build_option_trade_proposal(result, assessment)
    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.structure == "single_leg"
    assert proposal.legs[0].quantity == Decimal(1)


def test_non_roll_is_no_action_before_other_evidence() -> None:
    decision = evaluate_cboe_put(
        decision_date=date(2026, 10, 12),
        roll_date=date(2026, 10, 16),
        reference_state=UNKNOWN,
        quote_value=None,
        chain=None,
    )
    assert decision.verdict == NO_ACTION


def test_next_month_weekly_never_preempts_standard_monthly() -> None:
    as_of = date(2026, 10, 16)
    weekly = ExpirationCycle(date(2026, 11, 6), 21, False, True, as_of, EVIDENCE)
    monthly = ExpirationCycle(date(2026, 11, 20), 35, True, False, as_of, EVIDENCE)
    assert _next_month_expiration((weekly, monthly), as_of) == monthly.expiration_date


def test_missing_last_never_falls_back_to_index_quote_midpoint() -> None:
    quote = Quote(SPX.instrument, Decimal("4999"), Decimal("5001"), None, None, None, None, "USD")
    assert _spot(quote) is None


def test_roll_missing_or_late_reference_and_wrong_settlement_are_unknown() -> None:
    late = datetime(2026, 10, 16, 15, 0, tzinfo=UTC)
    assert (
        evaluate_cboe_put(
            decision_date=late.date(),
            roll_date=late.date(),
            reference_state=UNKNOWN,
            quote_value=Decimal("5000"),
            chain=_chain(_put("5000")),
        ).verdict
        == UNKNOWN
    )
    assert (
        evaluate_cboe_put(
            decision_date=ROLL.date(),
            roll_date=ROLL.date(),
            reference_state=PASS,
            quote_value=Decimal("5000"),
            chain=_chain(_put("5000", root="SPXW", settlement=SettlementStyle.PM)),
        ).verdict
        == UNKNOWN
    )
