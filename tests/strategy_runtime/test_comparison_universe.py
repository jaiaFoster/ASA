"""SPRINT-013 S13-04C: comparison-universe and sector-reference tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    CanonicalReturnObservation,
    EvidenceKind,
    EvidenceReference,
    SectorClassification,
    SecurityAssetType,
)
from strategy_runtime.comparison_universe import (
    ASSET_TYPE_BY_INSTRUMENT,
    GICS_SECTOR_TO_SPDR_BENCHMARK,
    SECTOR_BY_INSTRUMENT,
    approved_sector_id,
    select_comparison_universe_returns,
    select_sector_reference_returns,
)

PERIOD_START = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 1, 2, 21, 0, tzinfo=timezone.utc)
OTHER_PERIOD_START = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
OTHER_PERIOD_END = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)

EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "obs-1"),)


def _instrument(symbol: str) -> CanonicalInstrumentIdentity:
    return CanonicalInstrumentIdentity("symbol", symbol)


def _return(
    symbol: str,
    *,
    period: tuple[datetime, datetime] = (PERIOD_START, PERIOD_END),
    value: Decimal = Decimal("0.01"),
) -> CanonicalReturnObservation:
    start, end = period
    return CanonicalReturnObservation(
        instrument=_instrument(symbol),
        return_value=value,
        period_start=start,
        period_end=end,
        effective_time=end,
        evidence=EVIDENCE,
    )


EQUITY_PEERS = ["MSFT", "NVDA", "AMD", "AVGO", "INTC"]


class TestSelectComparisonUniverseReturns:
    def test_selects_qualifying_same_class_peers(self) -> None:
        candidates = tuple(_return(symbol) for symbol in EQUITY_PEERS)
        result = select_comparison_universe_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
        )
        assert result is not None
        assert {item.instrument for item in result.returns} == {
            _instrument(symbol) for symbol in EQUITY_PEERS
        }

    def test_excludes_the_subject_itself(self) -> None:
        candidates = tuple(_return(symbol) for symbol in [*EQUITY_PEERS, "AAPL"])
        result = select_comparison_universe_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
        )
        assert result is not None
        assert _instrument("AAPL") not in {item.instrument for item in result.returns}

    def test_excludes_a_different_asset_type(self) -> None:
        candidates = tuple(_return(symbol) for symbol in [*EQUITY_PEERS, "SPY", "QQQ"])
        result = select_comparison_universe_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
        )
        assert result is not None
        instruments = {item.instrument for item in result.returns}
        assert _instrument("SPY") not in instruments
        assert _instrument("QQQ") not in instruments

    def test_excludes_a_misaligned_return_period_without_excluding_others(self) -> None:
        misaligned = _return("MU", period=(OTHER_PERIOD_START, OTHER_PERIOD_END))
        candidates = (*[_return(symbol) for symbol in EQUITY_PEERS], misaligned)
        result = select_comparison_universe_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
        )
        assert result is not None
        instruments = {item.instrument for item in result.returns}
        assert _instrument("MU") not in instruments
        assert instruments == {_instrument(symbol) for symbol in EQUITY_PEERS}

    def test_excludes_an_unclassified_candidate_without_excluding_others(self) -> None:
        unclassified = _return("ZZZZ")
        candidates = (*[_return(symbol) for symbol in EQUITY_PEERS], unclassified)
        result = select_comparison_universe_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
        )
        assert result is not None
        assert _instrument("ZZZZ") not in {item.instrument for item in result.returns}

    def test_below_minimum_valid_members_is_none(self) -> None:
        candidates = tuple(_return(symbol) for symbol in EQUITY_PEERS[:4])
        result = select_comparison_universe_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
        )
        assert result is None

    def test_unclassified_subject_is_none(self) -> None:
        candidates = tuple(_return(symbol) for symbol in EQUITY_PEERS)
        result = select_comparison_universe_returns(
            _instrument("NOT_IN_UNIVERSE"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
        )
        assert result is None

    def test_custom_minimum_valid_members_is_honored(self) -> None:
        candidates = tuple(_return(symbol) for symbol in EQUITY_PEERS[:3])
        result = select_comparison_universe_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            candidates,
            ASSET_TYPE_BY_INSTRUMENT,
            minimum_valid_members=3,
        )
        assert result is not None
        assert len(result.returns) == 3


class TestSelectSectorReferenceReturns:
    def test_selects_aligned_sector_benchmark(self) -> None:
        benchmark = (_return("XLK"),)
        result = select_sector_reference_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            SECTOR_BY_INSTRUMENT,
            benchmark,
        )
        assert result is not None
        assert result.sector_id == "information_technology"
        assert result.returns[0].instrument == _instrument("XLK")

    def test_unclassified_subject_is_none(self) -> None:
        result = select_sector_reference_returns(
            _instrument("SPY"),
            (PERIOD_START, PERIOD_END),
            SECTOR_BY_INSTRUMENT,
            (_return("XLK"),),
        )
        assert result is None

    def test_unmapped_sector_is_none(self) -> None:
        sectors = {
            _instrument("AAPL"): SectorClassification("GICS", "2023", "99"),
        }
        result = select_sector_reference_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            sectors,
            (_return("XLK"),),
        )
        assert result is None

    def test_no_aligned_benchmark_return_is_none(self) -> None:
        misaligned = _return("XLK", period=(OTHER_PERIOD_START, OTHER_PERIOD_END))
        result = select_sector_reference_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            SECTOR_BY_INSTRUMENT,
            (misaligned,),
        )
        assert result is None

    def test_no_benchmark_returns_supplied_is_none(self) -> None:
        result = select_sector_reference_returns(
            _instrument("AAPL"),
            (PERIOD_START, PERIOD_END),
            SECTOR_BY_INSTRUMENT,
            (),
        )
        assert result is None


class TestApprovedSectorId:
    @pytest.mark.parametrize(
        ("gics_code", "expected"),
        [
            ("10", "energy"),
            ("15", "materials"),
            ("20", "industrials"),
            ("25", "consumer_discretionary"),
            ("30", "consumer_staples"),
            ("35", "health_care"),
            ("40", "financials"),
            ("45", "information_technology"),
            ("50", "communication_services"),
            ("55", "utilities"),
            ("60", "real_estate"),
        ],
    )
    def test_translates_every_approved_gics_code(self, gics_code: str, expected: str) -> None:
        sector = SectorClassification("GICS", "2023", gics_code)
        assert approved_sector_id(sector) == expected
        assert expected in GICS_SECTOR_TO_SPDR_BENCHMARK

    def test_unknown_gics_code_is_none(self) -> None:
        sector = SectorClassification("GICS", "2023", "99")
        assert approved_sector_id(sector) is None

    def test_non_gics_taxonomy_is_none(self) -> None:
        sector = SectorClassification("OTHER", "1", "45")
        assert approved_sector_id(sector) is None


class TestReferenceTables:
    def test_every_sector_classified_instrument_has_an_approved_sector_id(self) -> None:
        for sector in SECTOR_BY_INSTRUMENT.values():
            assert approved_sector_id(sector) is not None

    def test_every_asset_type_entry_is_equity_or_etf(self) -> None:
        assert set(ASSET_TYPE_BY_INSTRUMENT.values()) <= {
            SecurityAssetType.EQUITY,
            SecurityAssetType.ETF,
        }

    def test_no_etf_has_a_sector_classification(self) -> None:
        etfs = {
            instrument
            for instrument, asset_type in ASSET_TYPE_BY_INSTRUMENT.items()
            if asset_type is SecurityAssetType.ETF
        }
        assert etfs.isdisjoint(SECTOR_BY_INSTRUMENT.keys())
