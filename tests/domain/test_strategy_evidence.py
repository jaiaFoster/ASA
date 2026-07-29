"""WS5 provider-neutral canonical strategy-evidence contracts."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    ComparisonUniverseReturns,
    EvidenceKind,
    EvidenceReference,
    HistoricalSkewObservation,
    HistoricalSkewObservations,
    SectorReferenceReturns,
)

T0 = datetime(2026, 1, 2, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "canonical-input"),)


def _instrument(symbol: str) -> CanonicalInstrumentIdentity:
    return CanonicalInstrumentIdentity("figi", f"figi-{symbol}")


def _return(symbol: str, value: str) -> CanonicalReturnObservation:
    return CanonicalReturnObservation(
        _instrument(symbol),
        Decimal(value),
        T0,
        T0 + timedelta(days=20),
        T0 + timedelta(days=20),
        EVIDENCE,
    )


def test_historical_skew_is_immutable_ordered_and_single_instrument() -> None:
    later = HistoricalSkewObservation(
        _instrument("AAPL"), Decimal("0.20"), Decimal("0.30"), T0, EVIDENCE
    )
    earlier = HistoricalSkewObservation(
        _instrument("AAPL"),
        Decimal("0.10"),
        Decimal("0.15"),
        T0 - timedelta(days=1),
        EVIDENCE,
    )
    history = HistoricalSkewObservations((later, earlier))
    assert history.observations == (earlier, later)
    with pytest.raises(FrozenInstanceError):
        later.call_skew = Decimal("0")  # type: ignore[misc]
    with pytest.raises(ValueError, match="one instrument"):
        HistoricalSkewObservations(
            (
                earlier,
                HistoricalSkewObservation(
                    _instrument("MSFT"), Decimal("0.1"), Decimal("0.2"), T0, EVIDENCE
                ),
            )
        )


def test_return_collections_preserve_explicit_membership_and_period() -> None:
    universe = ComparisonUniverseReturns((_return("MSFT", "0.02"), _return("AAPL", "0.04")))
    assert tuple(item.instrument.value for item in universe.returns) == (
        "figi-AAPL",
        "figi-MSFT",
    )
    sector = SectorReferenceReturns("technology", universe.returns)
    assert sector.sector_id == "technology"
    assert sector.returns == universe.returns
