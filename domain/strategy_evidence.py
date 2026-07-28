"""Provider-neutral canonical evidence required by multi-subject strategies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain.operational import CanonicalInstrumentIdentity
from domain.references import EvidenceReference
from domain.values import require_finite_decimal, require_tz_aware


def _evidence(
    values: tuple[EvidenceReference, ...], owner: str
) -> tuple[EvidenceReference, ...]:
    if not values or len(values) != len(set(values)):
        raise ValueError(f"{owner}.evidence must be non-empty and unique")
    return tuple(
        sorted(values, key=lambda item: (item.kind.value, item.referenced_id, item.version or 0))
    )


@dataclass(frozen=True, slots=True)
class HistoricalSkewObservation:
    """One canonical call/put skew observation at a semantic effective time."""

    instrument: CanonicalInstrumentIdentity
    call_skew: Decimal
    put_skew: Decimal
    effective_time: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        require_finite_decimal(self.call_skew, "HistoricalSkewObservation", "call_skew")
        require_finite_decimal(self.put_skew, "HistoricalSkewObservation", "put_skew")
        require_tz_aware(self.effective_time, "HistoricalSkewObservation", "effective_time")
        object.__setattr__(
            self, "evidence", _evidence(self.evidence, "HistoricalSkewObservation")
        )


@dataclass(frozen=True, slots=True)
class HistoricalSkewObservations:
    """Deterministically ordered history; lookback selection is external policy."""

    observations: tuple[HistoricalSkewObservation, ...]

    def __post_init__(self) -> None:
        if not self.observations:
            raise ValueError("HistoricalSkewObservations cannot be empty")
        instruments = {item.instrument for item in self.observations}
        if len(instruments) != 1:
            raise ValueError("HistoricalSkewObservations must describe one instrument")
        ordered = tuple(sorted(self.observations, key=lambda item: item.effective_time))
        if len({item.effective_time for item in ordered}) != len(ordered):
            raise ValueError("HistoricalSkewObservations effective times must be unique")
        object.__setattr__(self, "observations", ordered)


@dataclass(frozen=True, slots=True)
class CanonicalReturnObservation:
    """One exact return supplied by canonical bars, without universe policy."""

    instrument: CanonicalInstrumentIdentity
    return_value: Decimal
    period_start: datetime
    period_end: datetime
    effective_time: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        require_finite_decimal(self.return_value, "CanonicalReturnObservation", "return_value")
        for field_name in ("period_start", "period_end", "effective_time"):
            require_tz_aware(
                getattr(self, field_name), "CanonicalReturnObservation", field_name
            )
        if self.period_end <= self.period_start or self.effective_time < self.period_end:
            raise ValueError("CanonicalReturnObservation temporal range is invalid")
        object.__setattr__(
            self, "evidence", _evidence(self.evidence, "CanonicalReturnObservation")
        )


@dataclass(frozen=True, slots=True)
class ComparisonUniverseReturns:
    """Returns for an explicitly supplied comparison universe."""

    returns: tuple[CanonicalReturnObservation, ...]

    def __post_init__(self) -> None:
        if not self.returns:
            raise ValueError("ComparisonUniverseReturns cannot be empty")
        ordered = tuple(
            sorted(
                self.returns,
                key=lambda item: (item.instrument.scheme, item.instrument.value),
            )
        )
        if len({item.instrument for item in ordered}) != len(ordered):
            raise ValueError("ComparisonUniverseReturns instruments must be unique")
        periods = {(item.period_start, item.period_end) for item in ordered}
        if len(periods) != 1:
            raise ValueError("ComparisonUniverseReturns must share one return period")
        object.__setattr__(self, "returns", ordered)


@dataclass(frozen=True, slots=True)
class SectorReferenceReturns:
    """Explicit sector reference members; sector membership is not inferred."""

    sector_id: str
    returns: tuple[CanonicalReturnObservation, ...]

    def __post_init__(self) -> None:
        if not self.sector_id or self.sector_id != self.sector_id.strip():
            raise ValueError("SectorReferenceReturns.sector_id must be normalized")
        normalized = ComparisonUniverseReturns(self.returns)
        object.__setattr__(self, "returns", normalized.returns)
