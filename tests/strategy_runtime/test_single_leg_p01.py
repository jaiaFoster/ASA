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
from strategy_runtime.trade_proposal import OptionTradeProposal, build_option_trade_proposal

NOW = datetime(2026, 9, 18, 16, tzinfo=UTC)
EXPIRY = date(2026, 10, 16)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "chain:1"),)
UNDERLYING = Security(
    Instrument(
        CanonicalInstrumentIdentity("index_root", "SPX"),
        InstrumentKind.INDEX,
        "SPX",
        "USD",
    ),
    "SPX",
    SecurityAssetType.INDEX,
    "CBOE",
)
PUT = OptionContract(
    CanonicalInstrumentIdentity("occ", "SPX-2026-10-16-5000-P-AM"),
    UNDERLYING,
    EXPIRY,
    Decimal("5000"),
    OptionType.PUT,
    Decimal("50"),
    Decimal("52"),
    None,
    100,
    1000,
    Decimal("-0.5"),
    None,
    None,
    None,
    None,
    None,
    NOW,
    EVIDENCE,
)
CHAIN = OptionChain("spx-chain", UNDERLYING, NOW, (PUT,), EVIDENCE)


@pytest.mark.parametrize("position", [OptionLegPosition.LONG, OptionLegPosition.SHORT])
@pytest.mark.parametrize("quantity", [Decimal("1"), Decimal("2.5")])
def test_p01_resolves_exact_long_short_unit_and_nonunit_quantity(
    position: OptionLegPosition, quantity: Decimal
) -> None:
    intent = OptionStructureIntent(
        "SPX",
        StructureKind.SINGLE_LEG,
        (
            OptionLegIntent(
                "put",
                OptionType.PUT,
                EXPIRY,
                position,
                quantity,
                selected_contract_identity=PUT.identity,
            ),
        ),
    )
    assessment = resolve_option_structure(
        intent=intent,
        chain=CHAIN,
        originating_result_identity="result-1",
        evidence_snapshot_identity="snapshot-1",
        assessed_at=NOW,
    )

    assert assessment.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    assert assessment.intended_structure_kind is StructureKind.SINGLE_LEG
    assert assessment.exact_legs[0].canonical_contract_identity == PUT.identity
    assert assessment.exact_legs[0].leg.position is position
    assert assessment.exact_legs[0].leg.quantity == quantity
    result = UniversalScreeningResult(
        "generic_short_put_fixture",
        "1.0.0",
        "SPX",
        "result-1",
        "opportunity-1",
        RowType.RESULT,
        "PASS",
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
    proposal = build_option_trade_proposal(result, assessment)
    assert isinstance(proposal, OptionTradeProposal)
    assert proposal.structure == "single_leg"
    assert proposal.legs[0].quantity == quantity


def test_p01_rejects_more_than_one_leg() -> None:
    leg = OptionLegIntent(
        "put",
        OptionType.PUT,
        EXPIRY,
        OptionLegPosition.SHORT,
        Decimal("1"),
        selected_contract_identity=PUT.identity,
    )
    with pytest.raises(ValueError, match="exactly one leg"):
        OptionStructureIntent("SPX", StructureKind.SINGLE_LEG, (leg, leg))
