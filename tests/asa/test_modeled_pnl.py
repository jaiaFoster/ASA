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
    OptionLegPosition,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import (
    deserialize_execution_assessment,
    serialize_execution_assessment,
)
from strategy_runtime.modeled_pnl import (
    MODEL_VERSION,
    ModeledPnLAssumptions,
    ModeledPnLSurface,
    ModeledPnLUnknown,
    model_front_expiration_pnl,
)
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)

NOW = datetime(2026, 9, 1, 15, tzinfo=UTC)
VALUATION = datetime(2026, 9, 18, 20, tzinfo=UTC)
FRONT = date(2026, 9, 18)
BACK = date(2026, 10, 16)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "chain-1", 1),)
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
        (Decimal(bid) + Decimal(ask)) / Decimal(2),
        10,
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


def _assessment():  # type: ignore[no-untyped-def]
    front = _contract(FRONT, "4.00", "4.20")
    back = _contract(BACK, "6.00", "6.20")
    chain = OptionChain("AAPL-chain", SECURITY, NOW, (front, back), EVIDENCE)
    intent = OptionStructureIntent(
        "AAPL",
        StructureKind.CALENDAR,
        (
            OptionLegIntent(
                "front",
                OptionType.CALL,
                FRONT,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_contract_identity=front.identity,
            ),
            OptionLegIntent(
                "back",
                OptionType.CALL,
                BACK,
                OptionLegPosition.LONG,
                Decimal(1),
                selected_contract_identity=back.identity,
            ),
        ),
    )
    return resolve_option_structure(
        intent=intent,
        chain=chain,
        originating_result_identity="result-1",
        evidence_snapshot_identity="snapshot-1",
        assessed_at=NOW,
    )


def _assumptions(assessment, **changes):  # type: ignore[no-untyped-def]
    back = max(assessment.exact_legs, key=lambda item: item.leg.contract.expiration)
    values = {
        "volatility_by_contract": ((back.leg.contract.identity, Decimal("0.30")),),
        "annual_risk_free_rate": Decimal("0.04"),
        "annual_dividend_yield": Decimal("0.01"),
        "contract_multiplier": Decimal("100"),
    }
    values.update(changes)
    return ModeledPnLAssumptions(**values)


def test_calendar_back_leg_retains_time_value_with_pinned_vector() -> None:
    assessment = _assessment()
    result = model_front_expiration_pnl(
        assessment=assessment,
        valuation_time=VALUATION,
        spot_reference=Decimal("200"),
        underlying_price_grid=(Decimal("180"), Decimal("200"), Decimal("220")),
        assumptions=_assumptions(assessment),
    )

    assert isinstance(result, ModeledPnLSurface)
    assert result.valuation_model_and_version == MODEL_VERSION
    assert tuple(item.modeled_pnl for item in result.points) == (
        Decimal("-118.83"),
        Decimal("484.73"),
        Decimal("-52.90"),
    )
    # At-the-money back-leg value exceeds intrinsic zero at front expiry.
    assert result.points[1].modeled_pnl > Decimal("-200.00")
    assert result.identity == result.identity


def test_assessment_round_trip_preserves_exact_identity_for_deferred_modeling() -> None:
    assessment = _assessment()

    restored = deserialize_execution_assessment(serialize_execution_assessment(assessment))

    assert restored == assessment
    assert restored.identity == assessment.identity


def test_unknown_rate_dividend_and_back_volatility_fail_typed() -> None:
    assessment = _assessment()
    cases = (
        (_assumptions(assessment, annual_risk_free_rate=None), "risk_free_rate_unknown"),
        (_assumptions(assessment, annual_dividend_yield=None), "dividend_yield_unknown"),
        (_assumptions(assessment, volatility_by_contract=()), "back_leg_volatility_unknown"),
    )

    for assumptions, reason in cases:
        result = model_front_expiration_pnl(
            assessment=assessment,
            valuation_time=VALUATION,
            spot_reference=Decimal("200"),
            underlying_price_grid=(Decimal("200"),),
            assumptions=assumptions,
        )
        assert isinstance(result, ModeledPnLUnknown)
        assert result.reason_code == reason


def test_midpoint_entry_is_required_and_never_called_executed_fill() -> None:
    assessment = _assessment()
    assert assessment.modeled_entry_economics is not None
    assert assessment.modeled_entry_economics.model_version == "midpoint-v1"
    assert "executed" not in assessment.modeled_entry_economics.model_version
