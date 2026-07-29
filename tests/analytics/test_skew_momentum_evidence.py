"""WS5 policy-free skew and momentum distribution vectors."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from analytics import (
    DERIVED_FACT_REGISTRY,
    compute_cross_sectional_momentum,
    compute_sector_relative_momentum,
    compute_skew_stretch_distributions,
)
from domain import MarketCapability
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
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "distribution-input"),)
INSTRUMENT = CanonicalInstrumentIdentity("figi", "figi-AAPL")


def _return(symbol: str, value: str) -> CanonicalReturnObservation:
    return CanonicalReturnObservation(
        CanonicalInstrumentIdentity("figi", f"figi-{symbol}"),
        Decimal(value),
        T0,
        T0 + timedelta(days=20),
        T0 + timedelta(days=20),
        EVIDENCE,
    )


def test_skew_distribution_exposes_both_methods_without_selecting_policy() -> None:
    history = HistoricalSkewObservations(
        tuple(
            HistoricalSkewObservation(
                INSTRUMENT,
                Decimal(call),
                Decimal(put),
                T0 + timedelta(days=index),
                EVIDENCE,
            )
            for index, (call, put) in enumerate(
                (("0.05", "0.30"), ("0.10", "0.25"), ("0.15", "0.20"), ("0.20", "0.15"))
            )
        )
    )
    call_percentile, call_zscore, put_percentile, put_zscore = (
        compute_skew_stretch_distributions(Decimal("0.18"), Decimal("0.18"), history)
    )
    assert call_percentile == Decimal("0.75")
    assert call_zscore > 0
    assert put_percentile == Decimal("0.25")
    assert put_zscore < 0


def test_comparison_and_sector_distributions_are_deterministic() -> None:
    universe = ComparisonUniverseReturns(
        (_return("MSFT", "0.02"), _return("NVDA", "0.08"), _return("GOOG", "0.04"))
    )
    sector = SectorReferenceReturns(
        "technology",
        (_return("MSFT", "0.02"), _return("NVDA", "0.08")),
    )
    assert compute_cross_sectional_momentum(Decimal("0.05"), universe) == Decimal(2) / Decimal(3)
    assert compute_sector_relative_momentum(Decimal("0.07"), sector) == Decimal("0.02")


def test_new_derived_facts_declare_complete_provider_neutral_capabilities() -> None:
    for identifier in ("cross_sectional_momentum", "sector_relative_momentum"):
        assert DERIVED_FACT_REGISTRY.get(identifier).required_capabilities == (
            MarketCapability.HISTORICAL_BARS_V1,
        )
    for identifier in ("skew_historical_percentile", "skew_historical_zscore"):
        assert DERIVED_FACT_REGISTRY.get(identifier).required_capabilities == (
            MarketCapability.OPTION_CHAIN_V1,
        )
