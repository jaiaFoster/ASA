"""STOCK-RUNTIME-001 STK-03: proves B001/B02's own dedicated scheduled
entry point (asa.scheduled_screening.run_scheduled_stock_benchmark_refresh)
actually runs both benchmarks end to end through real acquisition ->
resolution -> sealed snapshot -> generic knowledge composition -> subject-
first adapter -> persistence -- not merely a hand-built sealed snapshot
(tests/strategy_runtime/adapters/test_stock_benchmarks_subject_first.py
already proves the composition/adapter layer directly; this proves the
production entry point wires all of that together correctly).

Deliberately does NOT reuse tests/asa/_fixture_market_data_access.py's
MultiExpirationFixtureProvider: that fixture returns exactly one
HISTORICAL_BARS_V1 bar per fetch with no adjusted-close evidence at all,
which can never satisfy B002's ten-completed-month requirement -- this is
precisely why B001/B002 are kept out of PRODUCTION_SCREENING_UNIVERSE and
the SP500 cohort-claim path (see asa/scheduled_screening.py's own comment
beside STOCK_BENCHMARK_UNIVERSE). This file's own fixture provider returns
a genuine multi-month OHLCVSeries instead.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from asa.scheduled_screening import STOCK_BENCHMARK_UNIVERSE, run_scheduled_stock_benchmark_refresh
from domain import (
    AdjustedCloseBasis,
    EvidenceKind,
    EvidenceReference,
    MarketCapability,
    OHLCVBar,
    OHLCVSeries,
    Quote,
)
from market_data import CapabilityFulfillmentService, ProviderDependencies, load_market_data_config
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.fixture import DeterministicFixtureProvider
from market_data.registry import ProviderRegistry
from screening.live_acquisition import build_capability_registry, build_request_budget_manager
from strategy_runtime.market_data_planning import SubjectMarketDataAccess
from tests.asa.fakes import InMemoryLatestResultRepository, InMemoryObservationHistoryRepository
from tests.asa.test_scheduled_screening import _RecordingHistoricalSkewRepository

NOW = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)
_EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "fixture:SPY"),)


def _month_end_bar(instrument: object, months_back: int, adjusted_close: Decimal) -> OHLCVBar:
    total_months = NOW.year * 12 + (NOW.month - 1) - months_back
    year, month = divmod(total_months, 12)
    end_at = datetime(year, month + 1, 15, 12, 0, tzinfo=UTC)
    start_at = end_at - timedelta(days=1)
    close = Decimal("400") + Decimal(months_back)
    return OHLCVBar(
        instrument,
        86400,
        start_at,
        end_at,
        close,
        close + Decimal("2"),
        close - Decimal("2"),
        close,
        Decimal("1000000"),
        adjusted_close,
        AdjustedCloseBasis.SPLIT_ADJUSTED,
    )


class StockBenchmarkFixtureProvider(DeterministicFixtureProvider):
    """REAL_TIME_QUOTE_V1 above the SMA10M, plus a genuine ten-completed-
    month adjusted-close OHLCVSeries for HISTORICAL_BARS_V1 -- SMA10M mean
    of 401..410 == 405.5, quote last == 450 (> SMA10M, so B002 -> PASS).
    """

    def _value(self, subject, address, observed_at, evidence):  # noqa: ANN001
        instrument = subject.canonical_instrument
        capability = subject.requested_capability
        if capability is MarketCapability.REAL_TIME_QUOTE_V1:
            return Quote(
                instrument, None, None, Decimal("450"), None, None, None, instrument.currency
            )
        if capability is MarketCapability.HISTORICAL_BARS_V1:
            bars = tuple(
                _month_end_bar(instrument, months_back, Decimal("400") + months_back)
                for months_back in range(1, 11)
            )
            return OHLCVSeries(instrument, 86400, observed_at, bars)
        return super()._value(subject, address, observed_at, evidence)  # type: ignore[no-untyped-call]


def _build_stock_benchmark_access() -> dict[str, SubjectMarketDataAccess]:
    config = load_market_data_config({})
    (fixture_config,) = tuple(item for item in config.providers if item.enabled)

    def _factory(  # noqa: ANN001
        _config, _transport_factory, clock, subjects, *, budget_clock=None, rolling_window=None
    ):
        budget_manager = build_request_budget_manager((fixture_config,), clock)
        provider = StockBenchmarkFixtureProvider(
            fixture_config, ProviderDependencies(object(), clock, budget_manager)
        )
        provider_registry = ProviderRegistry((provider,))
        capability_registry = build_capability_registry(provider_registry)
        fulfillment = CapabilityFulfillmentService(
            provider_registry, capability_registry, budget_manager
        )
        return {
            symbol: SubjectMarketDataAccess(
                fulfillment, budget_manager, capability_registry, provider_registry.metadata()
            )
            for symbol in subjects
        }

    return _factory


def test_stock_benchmark_refresh_runs_both_pairs_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asa.scheduled_screening as scheduled_screening_module

    monkeypatch.setattr(
        scheduled_screening_module,
        "build_shared_market_data_access",
        _build_stock_benchmark_access(),
    )
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()

    outcomes = run_scheduled_stock_benchmark_refresh(
        repository=repository,
        history_repository=InMemoryObservationHistoryRepository(),
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        historical_skew_repository=_RecordingHistoricalSkewRepository(),
        now=NOW,
    )

    assert {(item.signal_id, item.symbol) for item in outcomes} == set(STOCK_BENCHMARK_UNIVERSE)
    assert all(item.error is None for item in outcomes)
    assert all(item.outcome != "missing_data" for item in outcomes)

    b001 = repository.get_one("B001", "SPY")
    assert b001 is not None
    assert b001.verdict == "PASS"

    b002 = repository.get_one("B002", "SPY")
    assert b002 is not None
    assert b002.verdict == "PASS"
    assert b002.metrics["sma_10m_completed_months"].native() == Decimal("405.5")


@pytest.mark.parametrize(
    ("tick", "expect_benchmarks"),
    [
        (datetime(2026, 10, 9, 20, 51, tzinfo=UTC), True),  # original cron window
        *(
            (datetime(2026, 10, 9, 21, minute, tzinfo=UTC), False)
            for minute in (1, 11, 21, 31, 41, 51)
        ),
        (datetime(2026, 11, 13, 21, 9, 59, tzinfo=UTC), True),  # delayed close tick
        (datetime(2026, 11, 13, 21, 10, tzinfo=UTC), False),
        (datetime(2026, 11, 27, 18, 1, tzinfo=UTC), True),  # early close
        (datetime(2026, 11, 27, 21, 1, tzinfo=UTC), False),
    ],
)
def test_extension_ticks_preserve_close_and_option_work(tick, expect_benchmarks):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from asa import scheduled_screening as scheduler
    from market_data.session_calendar import UsEquitySessionCalendar

    close = UsEquitySessionCalendar().session(tick.date()).closes_at
    repository = Mock()
    repository.get_one.return_value = SimpleNamespace(
        evaluation_state="pass",
        temporal=SimpleNamespace(
            usability_status="usable",
            market_session_date=tick.date(),
            observed_at=close,
            input_time_skew_seconds=0,
        ),
    )
    expected = STOCK_BENCHMARK_UNIVERSE if expect_benchmarks else ()
    assert (
        scheduler._scheduled_fixed_pairs(scheduler.SCHEDULED_FIXED_SUBJECT_PAIRS, tick, repository)
        == expected + scheduler.FIXED_SUBJECT_OPTION_UNIVERSE
    )


def test_missed_close_retries_only_unfinished_benchmarks(monkeypatch):
    from dataclasses import replace

    from asa import scheduled_screening as scheduler

    class Clock(datetime):
        tick = datetime(2026, 11, 13, 21, 11, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.tick.astimezone(tz)

    monkeypatch.setattr(scheduler, "datetime", Clock)
    monkeypatch.setattr(
        scheduler, "build_shared_market_data_access", _build_stock_benchmark_access()
    )
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "fixture")
    repo = InMemoryLatestResultRepository()

    def run():
        return run_scheduled_stock_benchmark_refresh(
            now=Clock.tick,
            repository=repo,
            history_repository=InMemoryObservationHistoryRepository(),
            historical_skew_repository=_RecordingHistoricalSkewRepository(),
            acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        )

    assert [x.signal_id for x in run()] == ["B001", "B002"]
    row = repo.get_one("B002", "SPY")
    assert row.evaluation_state == "pass"
    Clock.tick += timedelta(minutes=1)
    repo.upsert(
        replace(row, evaluation_state="missing_data", observed_at=Clock.tick, temporal=None)
    )
    Clock.tick += timedelta(minutes=10)
    assert [x.signal_id for x in run()] == ["B002"]
    Clock.tick += timedelta(minutes=10)
    assert run() == ()
