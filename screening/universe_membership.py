"""Effective-dated equity-universe membership used by screening.

Membership snapshots are maintenance inputs, never fetched during runtime.
Canonical instrument identity remains the existing ``("symbol", value)``
identity; this module only preserves membership provenance and effective time.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType

from domain import CanonicalInstrumentIdentity, SectorClassification, SecurityAssetType

GICS_TAXONOMY = "GICS"
GICS_TAXONOMY_VERSION = "2023"

# Taxonomy-level reference data at the boundary where the authoritative
# membership source's sector names become canonical domain classifications.
# This is deliberately not keyed by symbol or universe.
GICS_SECTOR_NAME_TO_CODE: Mapping[str, str] = MappingProxyType(
    {
        "Energy": "10",
        "Materials": "15",
        "Industrials": "20",
        "Consumer Discretionary": "25",
        "Consumer Staples": "30",
        "Health Care": "35",
        "Financials": "40",
        "Information Technology": "45",
        "Communication Services": "50",
        "Utilities": "55",
        "Real Estate": "60",
    }
)


@dataclass(frozen=True, slots=True)
class EquityUniverseMember:
    symbol: str
    security_name: str
    gics_sector: str
    gics_sub_industry: str
    cik: str

    def __post_init__(self) -> None:
        values = (
            self.symbol,
            self.security_name,
            self.gics_sector,
            self.gics_sub_industry,
            self.cik,
        )
        if any(not value or value != value.strip() for value in values):
            raise ValueError("equity universe member fields must be normalized non-empty text")


@dataclass(frozen=True, slots=True)
class EquityUniverseMembershipSnapshot:
    schema_version: str
    universe_id: str
    source_name: str
    source_url: str
    source_revision_id: int
    published_at: datetime
    effective_date: date
    members: tuple[EquityUniverseMember, ...]

    def __post_init__(self) -> None:
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        if self.effective_date != self.published_at.astimezone(UTC).date():
            raise ValueError("effective_date must equal the source revision date")
        symbols = tuple(member.symbol for member in self.members)
        if not symbols or symbols != tuple(sorted(symbols)) or len(symbols) != len(set(symbols)):
            raise ValueError("members must be non-empty, unique, and symbol-sorted")

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(member.symbol for member in self.members)

    @property
    def by_symbol(self) -> Mapping[str, EquityUniverseMember]:
        return MappingProxyType({member.symbol: member for member in self.members})


@dataclass(frozen=True, slots=True)
class EquityUniverseClassifications:
    asset_types: Mapping[CanonicalInstrumentIdentity, SecurityAssetType]
    sectors: Mapping[CanonicalInstrumentIdentity, SectorClassification]


@dataclass(frozen=True, slots=True)
class EffectiveUniverseMember:
    """Provider-neutral membership interval for a canonical instrument."""

    instrument: CanonicalInstrumentIdentity
    classification: str
    effective_from: date
    effective_through: date | None
    source_reference: str

    def __post_init__(self) -> None:
        if not self.classification or self.classification != self.classification.strip():
            raise ValueError("classification must be normalized non-empty text")
        if not self.source_reference or self.source_reference != self.source_reference.strip():
            raise ValueError("source_reference must be normalized non-empty text")
        if self.effective_through is not None and self.effective_through < self.effective_from:
            raise ValueError("effective_through cannot precede effective_from")

    def is_effective(self, as_of: date) -> bool:
        return self.effective_from <= as_of and (
            self.effective_through is None or as_of <= self.effective_through
        )


@dataclass(frozen=True, slots=True)
class EffectiveUniverseMembership:
    universe_id: str
    source_name: str
    source_url: str
    members: tuple[EffectiveUniverseMember, ...]

    def __post_init__(self) -> None:
        if not self.universe_id or not self.source_name or not self.source_url:
            raise ValueError("effective universe identity and source are required")
        ordered = tuple(
            sorted(
                self.members,
                key=lambda item: (
                    item.instrument.scheme,
                    item.instrument.value,
                    item.effective_from,
                ),
            )
        )
        if ordered != self.members or len({item.instrument for item in self.members}) != len(
            self.members
        ):
            raise ValueError("effective universe members must be unique and canonically sorted")

    def eligible_members(self, as_of: date) -> tuple[EffectiveUniverseMember, ...]:
        return tuple(item for item in self.members if item.is_effective(as_of))


_SELECT_SECTOR_SOURCE = (
    "https://www.ssga.com/us/en/individual/capabilities/equities/sector-investing/"
    "select-sector-etfs"
)


def _sector_etf(symbol: str, classification: str, inception: date) -> EffectiveUniverseMember:
    return EffectiveUniverseMember(
        CanonicalInstrumentIdentity("symbol", symbol),
        classification,
        inception,
        None,
        f"{_SELECT_SECTOR_SOURCE}#{symbol.lower()}",
    )


SELECT_SECTOR_SPDR_MEMBERSHIP = EffectiveUniverseMembership(
    "select_sector_spdr",
    "State Street Select Sector SPDR ETFs",
    _SELECT_SECTOR_SOURCE,
    tuple(
        sorted(
            (
                _sector_etf("XLB", "materials", date(1998, 12, 16)),
                _sector_etf("XLC", "communication_services", date(2018, 6, 18)),
                _sector_etf("XLE", "energy", date(1998, 12, 16)),
                _sector_etf("XLF", "financials", date(1998, 12, 16)),
                _sector_etf("XLI", "industrials", date(1998, 12, 16)),
                _sector_etf("XLK", "information_technology", date(1998, 12, 16)),
                _sector_etf("XLP", "consumer_staples", date(1998, 12, 16)),
                _sector_etf("XLRE", "real_estate", date(2015, 10, 7)),
                _sector_etf("XLU", "utilities", date(1998, 12, 16)),
                _sector_etf("XLV", "health_care", date(1998, 12, 16)),
                _sector_etf("XLY", "consumer_discretionary", date(1998, 12, 16)),
            ),
            key=lambda item: (item.instrument.scheme, item.instrument.value),
        )
    ),
)


def canonical_equity_classifications(
    snapshot: EquityUniverseMembershipSnapshot,
) -> EquityUniverseClassifications:
    """Project typed equity membership metadata into canonical classifications."""
    asset_types: dict[CanonicalInstrumentIdentity, SecurityAssetType] = {}
    sectors: dict[CanonicalInstrumentIdentity, SectorClassification] = {}
    for member in snapshot.members:
        instrument = CanonicalInstrumentIdentity("symbol", member.symbol)
        asset_types[instrument] = SecurityAssetType.EQUITY
        try:
            sector_code = GICS_SECTOR_NAME_TO_CODE[member.gics_sector]
        except KeyError:
            raise ValueError(
                f"unsupported GICS sector name in {snapshot.universe_id}: "
                f"{member.gics_sector!r}"
            ) from None
        sectors[instrument] = SectorClassification(
            GICS_TAXONOMY, GICS_TAXONOMY_VERSION, sector_code
        )
    return EquityUniverseClassifications(
        MappingProxyType(asset_types), MappingProxyType(sectors)
    )


def load_membership_snapshot(path: str) -> EquityUniverseMembershipSnapshot:
    with open(path, encoding="utf-8") as snapshot_file:
        payload = json.load(snapshot_file)
    members = tuple(
        sorted(
            (
                EquityUniverseMember(
                    symbol=item["Symbol"],
                    security_name=item["Security"],
                    gics_sector=item["GICS Sector"],
                    gics_sub_industry=item["GICS Sub-Industry"],
                    cik=item["CIK"],
                )
                for item in payload["members"]
            ),
            key=lambda item: item.symbol,
        )
    )
    return EquityUniverseMembershipSnapshot(
        schema_version=payload["schema_version"],
        universe_id=payload["universe_id"],
        source_name=payload["source_name"],
        source_url=payload["source_url"],
        source_revision_id=payload["source_revision_id"],
        published_at=datetime.fromisoformat(payload["published_at"].replace("Z", "+00:00")),
        effective_date=date.fromisoformat(payload["effective_date"]),
        members=members,
    )


SP500_MEMBERSHIP = load_membership_snapshot(
    f"{__file__.rsplit('/', 1)[0]}/universe_snapshots/sp500-2026-08-13.json"
)
