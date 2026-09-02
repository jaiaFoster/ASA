from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionContract,
    OptionLeg,
    OptionLegPosition,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategy_runtime.contract import StructureKind
from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
    ResolvedOptionLeg,
    SelectionDiagnostic,
)

NOW = datetime(2026, 9, 1, 15, tzinfo=UTC)


def _leg(expiration: date, strike: str, role: str) -> OptionLeg:
    instrument = Instrument(
        CanonicalInstrumentIdentity("symbol", "AAPL"),
        InstrumentKind.EQUITY,
        "AAPL",
        "USD",
    )
    security = Security(instrument, "AAPL", SecurityAssetType.EQUITY, "NASDAQ")
    contract = OptionContract(
        CanonicalInstrumentIdentity("occ", f"AAPL-{expiration}-{strike}-C"),
        security,
        expiration,
        Decimal(strike),
        OptionType.CALL,
        Decimal("2.00"),
        Decimal("2.20"),
        Decimal("2.10"),
        10,
        100,
        Decimal("0.50"),
        None,
        None,
        None,
        None,
        Decimal("0.30"),
        NOW,
        (EvidenceReference(EvidenceKind.OBSERVATION, "chain-observation", 1),),
    )
    return OptionLeg(contract, OptionLegPosition.LONG, Decimal(1), role)


def test_constructible_assessment_is_immutable_and_deterministic() -> None:
    legs = (
        ResolvedOptionLeg(_leg(date(2026, 9, 18), "200", "front"), Decimal("0.50")),
        ResolvedOptionLeg(_leg(date(2026, 10, 16), "200", "back"), Decimal("0.50")),
    )
    assessment = ExecutableStructureAssessment(
        "result-1",
        "AAPL",
        StructureKind.CALENDAR,
        ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED,
        legs,
        (SelectionDiagnostic("front", Decimal("0.50"), Decimal("0.50")),),
        None,
        "snapshot-1",
        NOW,
        available_structure_kind=StructureKind.CALENDAR,
    )

    assert assessment.identity == assessment.identity
    assert legs[0].canonical_contract_identity == legs[0].leg.contract.identity
    assert legs[0].midpoint == Decimal("2.10")
    with pytest.raises(FrozenInstanceError):
        assessment.subject = "MSFT"  # type: ignore[misc]


def test_calendar_cannot_silently_claim_diagonal_as_intended() -> None:
    diagonal_legs = (
        ResolvedOptionLeg(_leg(date(2026, 9, 18), "200", "front")),
        ResolvedOptionLeg(_leg(date(2026, 10, 16), "205", "back")),
    )

    alternate = ExecutableStructureAssessment(
        "result-1",
        "AAPL",
        StructureKind.CALENDAR,
        ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE,
        diagonal_legs,
        (),
        None,
        "snapshot-1",
        NOW,
        reason_code="same_strike_calendar_unavailable",
        available_structure_kind=StructureKind.CUSTOM,
    )
    assert alternate.status is ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE

    with pytest.raises(ValueError, match="exact intended legs"):
        ExecutableStructureAssessment(
            "result-1",
            "AAPL",
            StructureKind.CALENDAR,
            ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED,
            diagonal_legs,
            (),
            None,
            "snapshot-1",
            NOW,
            available_structure_kind=StructureKind.CUSTOM,
        )


def test_unknown_cannot_claim_resolved_legs() -> None:
    with pytest.raises(ValueError, match="cannot claim exact available legs"):
        ExecutableStructureAssessment(
            "result-1",
            "AAPL",
            StructureKind.VERTICAL,
            ExecutableStructureStatus.UNKNOWN,
            (ResolvedOptionLeg(_leg(date(2026, 9, 18), "200", "long")),),
            (),
            None,
            "snapshot-1",
            NOW,
            reason_code="stale_quote",
        )
