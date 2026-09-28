"""Provider-neutral point-in-time historical option evidence (A08)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from domain.financial import OptionCollection, OptionContract, financial_contract_to_data
from domain.operational import Instrument

if TYPE_CHECKING:
    from domain.demand_expansion import UnknownReason


@dataclass(frozen=True, slots=True)
class HistoricalOptionSnapshot:
    subject: Instrument
    observed_at: datetime
    fetched_at: datetime
    evidence_identity: str
    contracts: tuple[OptionContract, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.subject, Instrument) or not self.evidence_identity:
            raise ValueError("historical option snapshot identity is required")
        if any(
            value.tzinfo is None or value.utcoffset() is None
            for value in (self.observed_at, self.fetched_at)
        ):
            raise ValueError("historical option snapshot times must be timezone-aware")
        if self.fetched_at < self.observed_at:
            raise ValueError("historical option evidence cannot be fetched before observation")
        if not self.contracts:
            raise ValueError("historical option snapshot requires unique exact contracts")
        normalized = OptionCollection(self.contracts).contracts
        if any(item.observed_at > self.observed_at for item in self.contracts):
            raise ValueError("historical option contract cannot postdate its snapshot")
        if any(item.underlying.instrument != self.subject for item in normalized):
            raise ValueError("historical option contract underlying must match snapshot subject")
        object.__setattr__(self, "contracts", normalized)

    @property
    def identity(self) -> str:
        return _hash(
            (
                _instrument_data(self.subject),
                self.observed_at.isoformat(),
                self.fetched_at.isoformat(),
                self.evidence_identity,
                tuple(financial_contract_to_data(item) for item in self.contracts),
            )
        )


@dataclass(frozen=True, slots=True)
class HistoricalOptionPanel:
    subject: Instrument
    as_of: datetime
    snapshots: tuple[HistoricalOptionSnapshot, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.subject, Instrument):
            raise ValueError("historical option panel subject must be an Instrument")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("historical option panel as_of must be timezone-aware")
        if not self.snapshots:
            raise ValueError("historical option panel cannot be empty")
        if any(item.subject != self.subject for item in self.snapshots):
            raise ValueError("historical option panel subjects must match")
        if any(
            item.observed_at > self.as_of or item.fetched_at > self.as_of for item in self.snapshots
        ):
            raise ValueError("historical option panel cannot contain evidence unavailable as_of")
        times = tuple(item.observed_at for item in self.snapshots)
        if times != tuple(sorted(times)) or len(times) != len(set(times)):
            raise ValueError("historical option snapshots must be unique and chronological")

    @property
    def identity(self) -> str:
        return _hash(
            (
                _instrument_data(self.subject),
                self.as_of.isoformat(),
                tuple(item.identity for item in self.snapshots),
            )
        )


def _instrument_data(value: Instrument) -> tuple[object, ...]:
    sector = value.sector
    return (
        value.identity.scheme,
        value.identity.value,
        value.kind.value,
        value.display_symbol,
        value.currency,
        None if sector is None else (sector.taxonomy, sector.taxonomy_version, sector.code),
        None
        if value.underlying_identity is None
        else (value.underlying_identity.scheme, value.underlying_identity.value),
    )


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def historical_option_panel_or_unknown(
    subject: Instrument,
    as_of: datetime,
    snapshots: tuple[HistoricalOptionSnapshot, ...],
) -> HistoricalOptionPanel | UnknownReason:
    if not snapshots:
        from domain.demand_expansion import UnknownReason

        return UnknownReason("historical_option_panel_unavailable")
    return HistoricalOptionPanel(subject, as_of, snapshots)
