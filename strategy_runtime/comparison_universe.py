"""Comparison-universe membership and sector-relative evidence
(SPRINT-013 S13-04C).

Two Founder-approved policies (issue #255), implemented here as reusable,
pure functions and static reference data -- no live acquisition, no
strategy wiring, no persistence. Skew Momentum is the first consumer,
not the owner; any future strategy needing cross-sectional or
sector-relative return evidence can call these same functions.

comparison_universe:
    rule: same_instrument_class_within_active_configured_screening_universe
    exclude_subject: true
    same_return_period_required: true
    minimum_valid_members: 5
    insufficient_members: UNKNOWN

sector_reference:
    equities: canonical_GICS_sector_to_Select_Sector_SPDR_benchmark
    non_sector_or_broad_ETFs: UNKNOWN
    missing_mapping_or_data: UNKNOWN

Instrument class and sector are never invented here: both are existing
canonical domain facts (domain.SecurityAssetType, domain.
SectorClassification) -- this module classifies today's approved
universe using those existing types, it does not define a parallel one.
Neither function invents, infers, or guesses membership: candidate
returns are always caller-supplied (typically already-acquired canonical
bars for screening.live_acquisition.APPROVED_LIVE_UNIVERSE's own
members), and classification is always looked up from the static tables
below, never derived from a ticker string or any other heuristic. An
instrument absent from these tables is unclassified, and every consumer
must treat that as UNKNOWN, never a default.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    ComparisonUniverseReturns,
    SectorClassification,
    SectorReferenceReturns,
    SecurityAssetType,
)

GICS_TAXONOMY = "GICS"
GICS_TAXONOMY_VERSION = "2023"

# Founder-approved (issue #255): canonical GICS sector -> Select Sector
# SPDR benchmark ticker, keyed by the approved policy's own snake_case
# sector identifiers. Verbatim from the approved policy -- no sector or
# ticker invented or substituted here.
GICS_SECTOR_TO_SPDR_BENCHMARK: Mapping[str, str] = {
    "communication_services": "XLC",
    "consumer_discretionary": "XLY",
    "consumer_staples": "XLP",
    "energy": "XLE",
    "financials": "XLF",
    "health_care": "XLV",
    "industrials": "XLI",
    "materials": "XLB",
    "real_estate": "XLRE",
    "information_technology": "XLK",
    "utilities": "XLU",
}

# Standard top-level GICS sector codes (2023 structure) -> the approved
# policy's own snake_case sector identifiers above. A translation layer,
# not a second taxonomy: domain.SectorClassification.code carries the
# canonical GICS numeric code (this codebase's own established
# convention, see tests/instrument_helpers.py); this table is only how
# that canonical fact maps onto issue #255's own approved SPDR-mapping
# vocabulary.
_GICS_CODE_TO_APPROVED_SECTOR_ID: Mapping[str, str] = {
    "10": "energy",
    "15": "materials",
    "20": "industrials",
    "25": "consumer_discretionary",
    "30": "consumer_staples",
    "35": "health_care",
    "40": "financials",
    "45": "information_technology",
    "50": "communication_services",
    "55": "utilities",
    "60": "real_estate",
}


def _instrument(symbol: str) -> CanonicalInstrumentIdentity:
    return CanonicalInstrumentIdentity("symbol", symbol)


def _sector(gics_code: str) -> SectorClassification:
    return SectorClassification(GICS_TAXONOMY, GICS_TAXONOMY_VERSION, gics_code)


# Asset-type classification for every member of screening.live_acquisition.
# APPROVED_LIVE_UNIVERSE (SPRINT-011/UNI-001's own 30-symbol universe).
ASSET_TYPE_BY_INSTRUMENT: Mapping[CanonicalInstrumentIdentity, SecurityAssetType] = {
    # Mega-cap single names
    _instrument("AAPL"): SecurityAssetType.EQUITY,
    _instrument("MSFT"): SecurityAssetType.EQUITY,
    _instrument("NVDA"): SecurityAssetType.EQUITY,
    _instrument("AMD"): SecurityAssetType.EQUITY,
    _instrument("GOOGL"): SecurityAssetType.EQUITY,
    _instrument("AMZN"): SecurityAssetType.EQUITY,
    _instrument("META"): SecurityAssetType.EQUITY,
    _instrument("TSLA"): SecurityAssetType.EQUITY,
    _instrument("AVGO"): SecurityAssetType.EQUITY,
    _instrument("NFLX"): SecurityAssetType.EQUITY,
    # Financials
    _instrument("JPM"): SecurityAssetType.EQUITY,
    _instrument("BAC"): SecurityAssetType.EQUITY,
    _instrument("GS"): SecurityAssetType.EQUITY,
    # Healthcare
    _instrument("UNH"): SecurityAssetType.EQUITY,
    _instrument("LLY"): SecurityAssetType.EQUITY,
    # Industrials / consumer
    _instrument("HD"): SecurityAssetType.EQUITY,
    _instrument("WMT"): SecurityAssetType.EQUITY,
    _instrument("DIS"): SecurityAssetType.EQUITY,
    # Energy
    _instrument("XOM"): SecurityAssetType.EQUITY,
    _instrument("CVX"): SecurityAssetType.EQUITY,
    # Semis
    _instrument("INTC"): SecurityAssetType.EQUITY,
    _instrument("MU"): SecurityAssetType.EQUITY,
    # Major index / sector ETFs
    _instrument("SPY"): SecurityAssetType.ETF,
    _instrument("QQQ"): SecurityAssetType.ETF,
    _instrument("IWM"): SecurityAssetType.ETF,
    _instrument("DIA"): SecurityAssetType.ETF,
    _instrument("XLF"): SecurityAssetType.ETF,
    _instrument("XLE"): SecurityAssetType.ETF,
    _instrument("XLK"): SecurityAssetType.ETF,
    _instrument("GLD"): SecurityAssetType.ETF,
}

# GICS sector for every equity above. ETFs are deliberately absent --
# Founder-approved policy: "non_sector_or_broad_ETFs: UNKNOWN" (a fund is
# never itself GICS-sector-classified, including a single-sector SPDR
# fund, which exists to *be* a sector's benchmark, not to *belong to*
# one). GICS codes are well-established, public classifications for
# these large-cap names, not inferred from ticker or company name.
SECTOR_BY_INSTRUMENT: Mapping[CanonicalInstrumentIdentity, SectorClassification] = {
    _instrument("AAPL"): _sector("45"),
    _instrument("MSFT"): _sector("45"),
    _instrument("NVDA"): _sector("45"),
    _instrument("AMD"): _sector("45"),
    _instrument("GOOGL"): _sector("50"),
    _instrument("AMZN"): _sector("25"),
    _instrument("META"): _sector("50"),
    _instrument("TSLA"): _sector("25"),
    _instrument("AVGO"): _sector("45"),
    _instrument("NFLX"): _sector("50"),
    _instrument("JPM"): _sector("40"),
    _instrument("BAC"): _sector("40"),
    _instrument("GS"): _sector("40"),
    _instrument("UNH"): _sector("35"),
    _instrument("LLY"): _sector("35"),
    _instrument("HD"): _sector("25"),
    _instrument("WMT"): _sector("30"),
    _instrument("DIS"): _sector("50"),
    _instrument("XOM"): _sector("10"),
    _instrument("CVX"): _sector("10"),
    _instrument("INTC"): _sector("45"),
    _instrument("MU"): _sector("45"),
}


def approved_sector_id(sector: SectorClassification) -> str | None:
    """Translate a canonical GICS SectorClassification to issue #255's
    own approved snake_case sector identifier -- None (UNKNOWN) if this
    module's translation table has no entry, e.g. a taxonomy/code this
    approved policy never covered.
    """
    if sector.taxonomy != GICS_TAXONOMY:
        return None
    return _GICS_CODE_TO_APPROVED_SECTOR_ID.get(sector.code)


def select_comparison_universe_returns(
    subject: CanonicalInstrumentIdentity,
    subject_period: tuple[datetime, datetime],
    candidate_returns: tuple[CanonicalReturnObservation, ...],
    asset_types: Mapping[CanonicalInstrumentIdentity, SecurityAssetType],
    *,
    minimum_valid_members: int = 5,
) -> ComparisonUniverseReturns | None:
    """The approved comparison_universe rule, applied to caller-supplied
    candidate returns. Returns None (UNKNOWN) when the subject itself is
    unclassified or fewer than ``minimum_valid_members`` candidates
    qualify -- never a partial result silently treated as sufficient.

    A candidate qualifies only if all of: it is not the subject itself
    (exclude_subject); it shares the subject's own asset type
    (same_instrument_class_within_active_configured_screening_universe);
    it is itself classified; and its own return period matches the
    subject's exactly (same_return_period_required). One candidate
    failing any of these is simply excluded -- it never corrupts or
    excludes any other, still-valid candidate.
    """
    subject_asset_type = asset_types.get(subject)
    if subject_asset_type is None:
        return None
    qualifying = tuple(
        item
        for item in candidate_returns
        if item.instrument != subject
        and (item.period_start, item.period_end) == subject_period
        and asset_types.get(item.instrument) is subject_asset_type
    )
    if len(qualifying) < minimum_valid_members:
        return None
    return ComparisonUniverseReturns(qualifying)


def select_sector_reference_returns(
    subject: CanonicalInstrumentIdentity,
    subject_period: tuple[datetime, datetime],
    sectors: Mapping[CanonicalInstrumentIdentity, SectorClassification],
    benchmark_returns: tuple[CanonicalReturnObservation, ...],
) -> SectorReferenceReturns | None:
    """The approved sector_reference rule. Returns None (UNKNOWN) when the
    subject has no sector classification (an ETF, or an equity this
    module's own tables have no entry for), when its sector has no
    approved SPDR benchmark, or when no supplied benchmark return aligns
    to the subject's own return period -- never a substituted
    broad-market return standing in for a genuinely missing sector
    benchmark.
    """
    subject_sector = sectors.get(subject)
    if subject_sector is None:
        return None
    sector_id = approved_sector_id(subject_sector)
    if sector_id is None:
        return None
    benchmark_symbol = GICS_SECTOR_TO_SPDR_BENCHMARK.get(sector_id)
    if benchmark_symbol is None:
        return None
    aligned = tuple(
        item
        for item in benchmark_returns
        if item.instrument == _instrument(benchmark_symbol)
        and (item.period_start, item.period_end) == subject_period
    )
    if not aligned:
        return None
    return SectorReferenceReturns(sector_id, aligned)
