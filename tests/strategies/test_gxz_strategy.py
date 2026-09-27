from datetime import UTC, date, datetime
from decimal import Decimal

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategies.gxz_evaluation import FAIL, NO_ACTION, PASS, UNKNOWN, evaluate_gxz
from strategies.gxz_manifest import GXZ_MANIFEST, GXZ_STRATEGY_ID
from strategy_runtime.adapters.gxz import GXZ_CONTRACT
from strategy_runtime.adapters.gxz_subject_first import build_gxz_structure_intent
from strategy_runtime.contract import StructureKind
from strategy_runtime.option_structure_resolver import resolve_option_structure
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.trade_proposal import OptionTradeProposal, build_option_trade_proposal

NOW = datetime(2026, 10, 5, 20, tzinfo=UTC)
EA = date(2026, 10, 8)
EXPIRY = date(2026, 10, 9)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "obs", 1),)
SECURITY = Security(
    Instrument(CanonicalInstrumentIdentity("symbol", "ACME"), InstrumentKind.EQUITY, "ACME", "USD"),
    "ACME",
    SecurityAssetType.EQUITY,
    "NYSE",
)


def _contract(
    strike: str, option_type: OptionType, delta: str, volume: int | None
) -> OptionContract:
    suffix = option_type.value
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"ACME-{EXPIRY}-{strike}-{suffix}"),
        SECURITY,
        EXPIRY,
        Decimal(strike),
        option_type,
        Decimal("2"),
        Decimal("2.2"),
        None,
        volume,
        10,
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
    "gxz-chain",
    SECURITY,
    NOW,
    (
        _contract("100", OptionType.CALL, "0.50", 60),
        _contract("100", OptionType.PUT, "-0.50", 40),
        _contract("102", OptionType.CALL, "0.45", 20),
        _contract("102", OptionType.PUT, "-0.55", 30),
    ),
    EVIDENCE,
)


def _decision(**changes):  # type: ignore[no-untyped-def]
    values = dict(
        chain=CHAIN,
        spot=Decimal("100"),
        earnings_date=EA,
        earnings_confirmed=True,
        entry_date=NOW.date(),
        entry_session_state=PASS,
    )
    values.update(changes)
    return evaluate_gxz(**values)


def test_contract_manifest_and_assumptions_are_identity_bearing() -> None:
    assert GXZ_CONTRACT.strategy_id == GXZ_STRATEGY_ID
    assert GXZ_CONTRACT.structure is StructureKind.STRADDLE
    assert {item.assumption_id for item in GXZ_MANIFEST.assumptions} == {
        "RA-EV-01",
        "RA-EV-02",
        "IA-GXZ-PROVIDER-DELTA",
        "IA-GXZ-ENTRY-PRICE",
    }


def test_exact_multi_pair_quantities_and_volume_weights_are_deterministic() -> None:
    decision = _decision()
    assert decision.verdict == PASS
    assert [pair.call.strike for pair in decision.pairs] == [Decimal("100"), Decimal("102")]
    assert [pair.pair_weight for pair in decision.pairs] == [
        Decimal("2") / Decimal("3"),
        Decimal("1") / Decimal("3"),
    ]
    for pair in decision.pairs:
        assert pair.call_quantity > 0 and pair.put_quantity > 0
        assert pair.call_quantity * pair.call.delta + pair.put_quantity * pair.put.delta == 0  # type: ignore[operator]


def test_frozen_truth_table_preserves_fail_no_action_and_unknown() -> None:
    assert _decision(earnings_date=None).verdict == FAIL
    assert _decision(earnings_confirmed=False).verdict == UNKNOWN
    assert _decision(entry_session_state=FAIL).verdict == NO_ACTION
    assert _decision(entry_session_state=UNKNOWN).verdict == UNKNOWN
    assert _decision(earnings_confirmed=False, entry_session_state=FAIL).verdict == NO_ACTION
    assert _decision(spot=Decimal("4.99")).verdict == FAIL


def test_unknown_candidate_evidence_prevents_incomplete_all_pair_pass() -> None:
    chain = OptionChain(
        "gxz-chain-unknown",
        SECURITY,
        NOW,
        CHAIN.contracts
        + (
            _contract("101", OptionType.CALL, "0.50", None),
            _contract("101", OptionType.PUT, "-0.50", 10),
        ),
        EVIDENCE,
    )
    decision = _decision(chain=chain)
    assert decision.verdict == UNKNOWN
    assert decision.reason == "G_GXZ_PAIR_INPUT_UNKNOWN"
    assert decision.pairs == ()


def test_no_expiration_after_event_in_literal_calendar_window_fails() -> None:
    assert _decision(entry_date=date(2026, 9, 20)).verdict == FAIL


def test_exact_decision_projects_through_generic_trade_proposal() -> None:
    decision = _decision()
    result = UniversalScreeningResult(
        GXZ_STRATEGY_ID,
        GXZ_CONTRACT.version,
        "ACME",
        "gxz-result",
        "gxz-opportunity",
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
        NOW,
    )
    assessment = resolve_option_structure(
        intent=build_gxz_structure_intent("ACME", decision),
        chain=CHAIN,
        originating_result_identity=result.observation_id,
        evidence_snapshot_identity="snapshot-1",
        assessed_at=NOW,
    )
    proposal = build_option_trade_proposal(result, assessment)
    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.structure == "straddle"
    assert len(proposal.legs) == 4
    assert {leg.canonical_contract_identity for leg in proposal.legs} == {
        contract.identity for contract in CHAIN.contracts
    }
