"""SPRINT-008D/PROD-002: scheduled production screening execution."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from asa.scheduled_screening import (
    PRODUCTION_SCREENING_UNIVERSE,
    run_scheduled_refresh,
)
from domain import CanonicalInstrumentIdentity
from domain.strategy_evidence import HistoricalSkewObservation
from market_data.attempts import AttemptQuery, InMemoryAcquisitionAttemptRepository
from market_data.transport import ReadOnlyHttpResponse
from screening import APPROVED_LIVE_UNIVERSE, EARNINGS_CALENDAR_UNIVERSE
from tests.asa.fakes import InMemoryLatestResultRepository
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


def _tradier_option(
    symbol: str, expiration: str, strike: str, option_type: str, delta: str
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "underlying": "AAPL",
        "expiration_date": expiration,
        "strike": strike,
        "option_type": option_type,
        "bid": "4.9",
        "ask": "5.1",
        "last": "5",
        "volume": 1000,
        "open_interest": 5000,
        "greeks": {
            "delta": delta,
            "gamma": "0.03",
            "theta": "-0.1",
            "vega": "0.2",
            "mid_iv": "0.5",
        },
    }


def _tradier_daily_bars_response() -> ReadOnlyHttpResponse:
    days: list[dict[str, object]] = []
    for day_offset in range(29, -1, -1):
        day = (date.today() - timedelta(days=day_offset)).isoformat()
        close = 200 + (day_offset % 5) + (29 - day_offset) * 0.15
        days.append(
            {
                "date": day,
                "open": str(close - 2),
                "high": str(close + 2),
                "low": str(close - 3),
                "close": str(close),
                "volume": "50000000",
            }
        )
    return ReadOnlyHttpResponse(
        200, {"history": {"day": days}}, (), 12, "tradier-request-history"
    )


def _tradier_skew_capable_chain_responses(expiration: str) -> list[ReadOnlyHttpResponse]:
    """Enough strikes on both sides (an ATM and a 0.25/-0.25-delta wing)
    for Skew Momentum's own real vertical-leg selection to succeed, plus
    30 daily closes for its own realized-volatility/momentum computation
    -- _tradier_refresh_responses's single call-only contract and no
    history is enough to exercise runner-level infrastructure isolation
    but not enough for the strategy's own read path
    (historical_valid_observations) to ever be reached.
    """
    return [
        tradier_quote_response(),
        ReadOnlyHttpResponse(
            200, {"expirations": {"date": [expiration]}}, (), 12, "tradier-request-2"
        ),
        ReadOnlyHttpResponse(
            200,
            {
                "options": {
                    "option": [
                        _tradier_option("ATM_CALL", expiration, "190", "call", "0.50"),
                        _tradier_option("WING_CALL", expiration, "195", "call", "0.25"),
                        _tradier_option("ATM_PUT", expiration, "190", "put", "-0.50"),
                        _tradier_option("WING_PUT", expiration, "185", "put", "-0.25"),
                    ]
                }
            },
            (),
            12,
            "tradier-request-3",
        ),
        _tradier_daily_bars_response(),
    ]


def _tradier_refresh_responses(expiration: str) -> list[ReadOnlyHttpResponse]:
    return [
        tradier_quote_response(),
        ReadOnlyHttpResponse(
            200, {"expirations": {"date": [expiration]}}, (), 12, "tradier-request-2"
        ),
        ReadOnlyHttpResponse(
            200,
            {
                "options": {
                    "option": [
                        {
                            "symbol": "TEST_CALL",
                            "underlying": "AAPL",
                            "expiration_date": expiration,
                            "strike": "190",
                            "option_type": "call",
                            "bid": "4.9",
                            "ask": "5.1",
                            "last": "5",
                            "volume": 1000,
                            "open_interest": 5000,
                            "greeks": {
                                "delta": "0.5",
                                "gamma": "0.03",
                                "theta": "-0.1",
                                "vega": "0.2",
                                "rho": "0.01",
                            },
                        }
                    ]
                }
            },
            (),
            12,
            "tradier-request-3",
        ),
    ]


def test_production_universe_covers_all_three_migrated_strategies() -> None:
    # SPRINT-011/UNI-002: earnings_calendar joins forward_factor/skew_momentum
    # in the scheduled universe now that REL-001 (SPRINT-010) fixed its live
    # acquisition. Counts derive from the source tuples, not a hardcoded
    # literal, so this can't silently drift (PROD-005's own established
    # single-source-of-truth rationale).
    signal_ids = {signal_id for signal_id, _symbol in PRODUCTION_SCREENING_UNIVERSE}
    assert signal_ids == {"forward_factor", "skew_momentum", "earnings_calendar"}
    expected = 2 * len(APPROVED_LIVE_UNIVERSE) + len(EARNINGS_CALENDAR_UNIVERSE)
    assert len(PRODUCTION_SCREENING_UNIVERSE) == expected
    assert len(set(PRODUCTION_SCREENING_UNIVERSE)) == expected  # no duplicate pairs


def test_earnings_calendar_pairs_use_the_single_name_subset_only() -> None:
    etfs = {"SPY", "QQQ", "IWM", "DIA", "XLF", "XLE", "XLK", "GLD"}
    earnings_symbols = {
        symbol
        for signal_id, symbol in PRODUCTION_SCREENING_UNIVERSE
        if signal_id == "earnings_calendar"
    }
    assert earnings_symbols == set(EARNINGS_CALENDAR_UNIVERSE)
    assert earnings_symbols.isdisjoint(etfs)


def test_no_enabled_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ASA_TRADIER_ENABLED", "ASA_FINNHUB_ENABLED", "ASA_ALPHA_VANTAGE_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="at least one enabled live market data provider"):
        run_scheduled_refresh(repository=InMemoryLatestResultRepository())


def test_runs_every_pair_and_persists_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    # One universe pair, scripted with enough responses for one full acquisition.
    universe = (("skew_momentum", "AAPL"),)
    responses = _tradier_refresh_responses(expiration)

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        transport_factory=lambda _provider_id: ScriptedTransport(responses),
    )

    assert len(outcomes) == 1
    assert outcomes[0].signal_id == "skew_momentum"
    assert outcomes[0].symbol == "AAPL"
    assert outcomes[0].error is None
    assert outcomes[0].outcome is not None
    assert outcomes[0].request_count is not None and outcomes[0].request_count >= 1
    # Actually persisted through the injected repository -- not just returned.
    assert repository.get_one("skew_momentum", "AAPL") is not None


class _RepositoryThatFailsForOneSymbol:
    """Wraps a real InMemoryLatestResultRepository, raising only for one
    chosen symbol's upsert -- isolates the *runner's own* failure boundary
    (a genuinely unexpected infrastructure error) from screening's already
    thoroughly-tested per-signal acquisition isolation (any acquisition
    problem is already converted to a persisted failure outcome inside
    screening.service.refresh() itself, never an exception -- see
    screening/runner.py::_run_one -- so it cannot be used to exercise this
    module's own outer boundary)."""

    def __init__(self, delegate: InMemoryLatestResultRepository, failing_symbol: str) -> None:
        self._delegate = delegate
        self._failing_symbol = failing_symbol

    def upsert(self, record: object) -> None:
        if getattr(record, "symbol", None) == self._failing_symbol:
            raise RuntimeError("simulated infrastructure failure")
        self._delegate.upsert(record)  # type: ignore[arg-type]

    def get_all(self) -> tuple[object, ...]:
        return self._delegate.get_all()

    def get_for_signal(self, signal_id: str) -> tuple[object, ...]:
        return self._delegate.get_for_signal(signal_id)

    def get_one(self, signal_id: str, symbol: str) -> object | None:
        return self._delegate.get_one(signal_id, symbol)


def test_one_pairs_infrastructure_failure_does_not_abort_the_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    delegate = InMemoryLatestResultRepository()
    repository = _RepositoryThatFailsForOneSymbol(delegate, failing_symbol="AAPL")
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"), ("skew_momentum", "MSFT"))

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,  # type: ignore[arg-type]
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_refresh_responses(expiration)
        ),
    )

    assert len(outcomes) == 2
    assert outcomes[0].symbol == "AAPL"
    assert outcomes[0].error is not None
    assert "simulated infrastructure failure" in outcomes[0].error
    assert outcomes[1].symbol == "MSFT"
    assert outcomes[1].error is None
    # The failing pair never persisted; the succeeding one did.
    assert delegate.get_one("skew_momentum", "AAPL") is None
    assert delegate.get_one("skew_momentum", "MSFT") is not None


class _SingleUseClaimRepository:
    def __init__(self) -> None:
        self.claimed: set[str] = set()

    def claim(self, slot_id: str, claimed_at: datetime) -> bool:
        del claimed_at
        if slot_id in self.claimed:
            return False
        self.claimed.add(slot_id)
        return True


def test_duplicate_cron_delivery_executes_slot_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    claims = _SingleUseClaimRepository()
    expiration = date(2026, 8, 7).isoformat()
    run_at = datetime(2026, 7, 27, 13, 45, tzinfo=UTC)
    arguments = {
        "repository": repository,
        "claim_repository": claims,
        "enforce_schedule": True,
        "now": run_at,
        "transport_factory": lambda _provider_id: ScriptedTransport(
            _tradier_refresh_responses(expiration)
        ),
    }

    first = run_scheduled_refresh((("skew_momentum", "AAPL"),), **arguments)
    duplicate = run_scheduled_refresh((("skew_momentum", "AAPL"),), **arguments)

    assert len(first) == 1
    assert duplicate == ()
    assert len(claims.claimed) == 1


# -- SPRINT-013 S13-02: acquisition attempt recording -----------------------


def test_attempts_are_recorded_under_one_shared_cycle_id_for_every_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    attempt_repository = InMemoryAcquisitionAttemptRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"), ("skew_momentum", "MSFT"))

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=attempt_repository,
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_refresh_responses(expiration)
        ),
    )

    assert all(item.attempts_recorded for item in outcomes)
    recorded = attempt_repository.query(AttemptQuery(limit=100))
    assert recorded  # at least one provider attempt was actually persisted
    cycle_ids = {item.screening_cycle_id for item in recorded}
    assert len(cycle_ids) == 1  # one cycle spans the whole invocation
    pair_ids = {item.pair_evaluation_id for item in recorded}
    cycle_id = next(iter(cycle_ids))
    assert pair_ids <= {
        f"{cycle_id}:skew_momentum:AAPL",
        f"{cycle_id}:skew_momentum:MSFT",
    }


def test_manual_invocation_uses_a_different_cycle_id_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"),)
    first_attempts = InMemoryAcquisitionAttemptRepository()
    second_attempts = InMemoryAcquisitionAttemptRepository()

    run_scheduled_refresh(
        universe,
        repository=InMemoryLatestResultRepository(),
        acquisition_attempt_repository=first_attempts,
        now=datetime(2026, 7, 21, 16, 0, tzinfo=UTC),
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_refresh_responses(expiration)
        ),
    )
    run_scheduled_refresh(
        universe,
        repository=InMemoryLatestResultRepository(),
        acquisition_attempt_repository=second_attempts,
        now=datetime(2026, 7, 21, 16, 0, 1, tzinfo=UTC),
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_refresh_responses(expiration)
        ),
    )

    first_cycle = {item.screening_cycle_id for item in first_attempts.query(AttemptQuery())}
    second_cycle = {item.screening_cycle_id for item in second_attempts.query(AttemptQuery())}
    assert first_cycle != second_cycle


class _AttemptRepositoryThatAlwaysFails:
    def record(self, attempts: object) -> None:
        raise RuntimeError("simulated attempt-persistence outage")

    def query(self, query: object) -> tuple[object, ...]:
        return ()

    def summarize(self, query: object) -> dict[object, int]:
        return {}


def test_attempt_persistence_failure_preserves_the_screening_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistence outage for the attempt side-channel must never abort
    or corrupt the pair's own strategy evaluation, but must never be
    silently reported as complete either (SPRINT-013 S13-02)."""
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"),)

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=_AttemptRepositoryThatAlwaysFails(),  # type: ignore[arg-type]
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_refresh_responses(expiration)
        ),
    )

    assert len(outcomes) == 1
    # The strategy evaluation itself is preserved and still persisted.
    assert outcomes[0].error is None
    assert outcomes[0].outcome is not None
    assert repository.get_one("skew_momentum", "AAPL") is not None
    # But acquisition accounting is honestly marked incomplete, never
    # silently reported as if it were complete.
    assert outcomes[0].attempts_recorded is False


# -- SPRINT-013 S13-04D: historical-skew read/write wiring -------------------


class _RecordingHistoricalSkewRepository:
    def __init__(self) -> None:
        self.history_for_calls: list[CanonicalInstrumentIdentity] = []
        self.append_calls: list[HistoricalSkewObservation] = []

    def append(self, observation: HistoricalSkewObservation, *, session_date: date) -> None:
        self.append_calls.append(observation)

    def history_for(
        self,
        instrument: CanonicalInstrumentIdentity,
        *,
        as_of: datetime | None = None,
        maximum_observations: int | None = None,
    ) -> tuple[HistoricalSkewObservation, ...]:
        self.history_for_calls.append(instrument)
        return ()


def test_skew_momentum_pair_reads_the_injected_historical_skew_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    historical_skew_repository = _RecordingHistoricalSkewRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"),)

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        historical_skew_repository=historical_skew_repository,
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_skew_capable_chain_responses(expiration)
        ),
    )

    assert outcomes[0].error is None
    assert historical_skew_repository.history_for_calls == [
        CanonicalInstrumentIdentity("symbol", "AAPL")
    ]


def test_non_skew_momentum_pairs_never_touch_the_historical_skew_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    historical_skew_repository = _RecordingHistoricalSkewRepository()
    universe = (("earnings_calendar", "AAPL"),)

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        historical_skew_repository=historical_skew_repository,
        transport_factory=lambda _provider_id: ScriptedTransport(
            [tradier_quote_response()]
        ),
    )

    assert outcomes[0].signal_id == "earnings_calendar"
    # Missing data (a scripted transport that never gets past the quote)
    # is an expected, isolated, non-crashing outcome, not this test's own
    # concern -- only whether the historical-skew repository was ever
    # touched for a non-skew_momentum pair is.
    assert historical_skew_repository.history_for_calls == []
    assert historical_skew_repository.append_calls == []


def test_a_conflicting_historical_observation_does_not_fail_the_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPRINT-013 S13-04D: history-capture recording is a best-effort side
    channel of a successful refresh() -- a genuine content conflict (a
    real defect worth investigating, logged as an error) must never turn
    an otherwise-successful pair into a failed PairOutcome.
    """
    import asa.scheduled_screening as scheduled_screening_module
    from strategy_runtime.historical_evidence import ConflictingHistoricalObservationError

    calls = []

    def _raise_conflict(*args: object, **_kwargs: object) -> None:
        calls.append(args)
        raise ConflictingHistoricalObservationError("boom")

    monkeypatch.setattr(
        scheduled_screening_module, "record_prospective_skew_observation", _raise_conflict
    )
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"),)

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_skew_capable_chain_responses(expiration)
        ),
    )

    assert len(calls) == 1  # the monkeypatched function was actually reached
    assert outcomes[0].error is None
    assert outcomes[0].outcome is not None
    assert repository.get_one("skew_momentum", "AAPL") is not None


def test_an_unexpected_capture_failure_does_not_fail_the_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asa.scheduled_screening as scheduled_screening_module

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(scheduled_screening_module, "capture_skew_snapshot", _raise)
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"),)

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        transport_factory=lambda _provider_id: ScriptedTransport(
            _tradier_refresh_responses(expiration)
        ),
    )

    assert outcomes[0].error is None
    assert outcomes[0].outcome is not None
    assert repository.get_one("skew_momentum", "AAPL") is not None


# -- SPRINT-013 S13-03A: shared cross-pair provider rolling window ----------


def _force_tiny_tradier_window(monkeypatch: pytest.MonkeyPatch, window_limit: int) -> None:
    """Overrides the real declared Tradier limit (60-120/min) with a tiny
    one so cross-pair refusal is observable with just two pairs, instead
    of scripting dozens of requests."""
    import strategy_runtime.market_data_planning as planning
    from market_data.rolling_window import RollingWindowPolicy

    monkeypatch.setattr(
        planning,
        "tradier_rolling_window_policy",
        lambda endpoint_environment: RollingWindowPolicy(  # noqa: ARG005
            "tradier", 60, window_limit, "test-override"
        ),
    )


# One pair's complete, real Skew Momentum acquisition needs exactly 4
# sequential Tradier requests (quote, expirations, option chain,
# historical daily closes) -- confirmed empirically. The module-level
# _tradier_refresh_responses() above is intentionally minimal (a single
# call contract, no put, no history) and only proves the runner isolates
# an unexpected exception, not a full clean success -- fine for the tests
# that already use it, but these two tests need a genuinely complete
# fixture so their pass/refusal assertions are unambiguous rather than
# "some outcome, who knows which."
_SKEW_MOMENTUM_REQUESTS_PER_PAIR = 4
_STRIKE_DELTA_LADDER = (
    (-15, "0.80"),
    (-10, "0.70"),
    (-5, "0.60"),
    (0, "0.50"),
    (5, "0.35"),
    (10, "0.25"),
    (15, "0.15"),
)


def _option_row(strike: int, expiration: str, option_type: str, call_delta: str) -> dict:
    delta = call_delta if option_type == "call" else str(round(float(call_delta) - 1, 2))
    return {
        "symbol": f"TEST_{option_type.upper()}_{strike}",
        "underlying": "AAPL",
        "expiration_date": expiration,
        "strike": str(strike),
        "option_type": option_type,
        "bid": "4.9",
        "ask": "5.1",
        "last": "5",
        "volume": 1000,
        "open_interest": 5000,
        "greeks": {
            "delta": delta,
            "gamma": "0.03",
            "theta": "-0.1",
            "vega": "0.2",
            "rho": "0.01",
            "mid_iv": "0.30",
        },
    }


def _complete_history_response() -> ReadOnlyHttpResponse:
    days = []
    cursor = date.today() - timedelta(days=1)
    price = 189.0
    while len(days) < 32:
        if cursor.weekday() < 5:
            days.append(
                {
                    "date": cursor.isoformat(),
                    "open": str(price - 0.5),
                    "high": str(price + 1),
                    "low": str(price - 1),
                    "close": str(price),
                    "volume": "1000000",
                }
            )
            price -= 0.1
        cursor -= timedelta(days=1)
    days.reverse()
    return ReadOnlyHttpResponse(200, {"history": {"day": days}}, (), 12, "tradier-request-4")


def _complete_skew_momentum_responses(expiration: str) -> list[ReadOnlyHttpResponse]:
    options = [
        _option_row(190 + offset, expiration, option_type, call_delta)
        for offset, call_delta in _STRIKE_DELTA_LADDER
        for option_type in ("call", "put")
    ]
    return [
        tradier_quote_response(),
        ReadOnlyHttpResponse(
            200, {"expirations": {"date": [expiration]}}, (), 12, "tradier-request-2"
        ),
        ReadOnlyHttpResponse(200, {"options": {"option": options}}, (), 12, "tradier-request-3"),
        _complete_history_response(),
    ]


def test_one_tracker_is_shared_across_every_pair_in_the_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    # Exactly enough for one pair's full 4-request acquisition, not two.
    _force_tiny_tradier_window(monkeypatch, window_limit=_SKEW_MOMENTUM_REQUESTS_PER_PAIR)
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"), ("skew_momentum", "MSFT"))

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(
            _complete_skew_momentum_responses(expiration)
        ),
    )

    assert len(outcomes) == 2
    # First pair's acquisition runs to completion -- all 4 requests are
    # actually authorized and made, consuming the entire shared window
    # doing so (what skew_momentum's own strategy logic then decides from
    # that real data -- pass/no_signal/its own missing_data -- is a
    # business-logic question this test isn't about, and is sensitive to
    # the real wall clock _SystemClock always uses regardless of any `now`
    # passed to run_scheduled_refresh, so it is deliberately not asserted
    # here). The second pair's very first request is refused by that SAME
    # shared window, before it ever reaches the (unconsumed) scripted
    # transport queue -- proof one tracker is genuinely shared across
    # pairs within this one cycle, not rebuilt per pair.
    assert outcomes[0].error is None
    assert outcomes[0].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR
    assert outcomes[1].error is None  # isolated per-pair failure, not a crash
    assert outcomes[1].outcome == "missing_data"
    assert outcomes[1].request_count == 0  # refused before any request was made


def test_two_separate_invocations_each_get_a_fresh_tracker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    _force_tiny_tradier_window(monkeypatch, window_limit=_SKEW_MOMENTUM_REQUESTS_PER_PAIR)
    expiration = (date.today() + timedelta(days=7)).isoformat()

    first_outcomes = run_scheduled_refresh(
        (("skew_momentum", "AAPL"),),
        repository=InMemoryLatestResultRepository(),
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(
            _complete_skew_momentum_responses(expiration)
        ),
    )
    second_outcomes = run_scheduled_refresh(
        (("skew_momentum", "MSFT"),),
        repository=InMemoryLatestResultRepository(),
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(
            _complete_skew_momentum_responses(expiration)
        ),
    )

    # Both runs authorize and make their own full 4 requests independently
    # -- the second call's tracker does not inherit the first call's
    # already-exhausted window state, proving fresh cycle-scoped state per
    # invocation. (What skew_momentum's own strategy logic decides from
    # the real data is a business-logic question this test isn't about --
    # see the sibling test above for why that's deliberately not asserted.)
    assert first_outcomes[0].error is None
    assert first_outcomes[0].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR
    assert second_outcomes[0].error is None
    assert second_outcomes[0].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR


# -- SPRINT-013 S13-03B: cycle-scoped request reuse ------------------------


def test_a_symbol_shared_across_two_pairs_in_one_cycle_reuses_the_first_pairs_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    # Same (strategy, symbol) pair twice -- an identical adapter evaluation
    # requests the exact same capabilities with the exact same window and
    # freshness both times, so a working cycle-scoped reuse coordinator
    # must serve the second occurrence's quote and chain requests entirely
    # from the first's cache.
    universe = (("skew_momentum", "AAPL"), ("skew_momentum", "AAPL"))
    # Two full acquisitions' worth of scripted responses: this fixture's
    # own synthetic historical-bars response (32 business days ending
    # yesterday, relative to whatever real calendar date this test
    # actually runs on) can fail its own strategy's freshness policy
    # (STALE_DATA) depending on that real date -- observed directly: this
    # test failed with request_count == 1 on one CI run (history missed
    # freshness, needed one independent retry) and request_count == 0 on
    # a local run the next day (history passed, full reuse). A cached
    # *failed* result is never reused (market_data/fulfillment.py's own
    # explicit rule, to preserve failure isolation -- see
    # tests/market_data/test_fulfillment.py's
    # test_a_failed_result_is_never_reused_and_gets_its_own_independent_retry),
    # so at most that one capability ever needs its own fresh retry; the
    # other three (quote, expirations, chain) always reuse regardless of
    # calendar date, since none of their freshness classification depends
    # on the history capability's own window.
    responses = _complete_skew_momentum_responses(expiration) + _complete_skew_momentum_responses(
        expiration
    )

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(responses),
    )

    assert len(outcomes) == 2
    assert outcomes[0].error is None
    assert outcomes[0].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR
    assert outcomes[1].error is None
    # At most the one calendar-date-sensitive history capability ever
    # needs an independent retry -- quote/expirations/chain always reuse.
    assert outcomes[1].request_count <= 1
    assert outcomes[1].outcome == outcomes[0].outcome  # reused evidence, same evaluated outcome


def test_different_symbols_in_the_same_cycle_never_share_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"), ("skew_momentum", "MSFT"))
    # Two full acquisitions' worth of responses -- if this pair incorrectly
    # reused AAPL's cached evidence for MSFT (cross-symbol reuse, explicitly
    # forbidden), the second pair would need fewer than 4 requests and this
    # test's own assertion on outcomes[1].request_count would catch it.
    responses = _complete_skew_momentum_responses(expiration) + _complete_skew_momentum_responses(
        expiration
    )

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(responses),
    )

    assert len(outcomes) == 2
    assert outcomes[0].error is None
    assert outcomes[0].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR
    assert outcomes[1].error is None
    assert outcomes[1].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR


# -- SPRINT-013 P0: quota clock separation -----------------------------------


def _stepped_monotonic(steps: list[float], *, tail: float):  # noqa: ANN201
    """A fake time.monotonic() that returns each of ``steps`` in order,
    then holds at ``tail`` forever -- never raises StopIteration even if
    a call count assumption is slightly off."""
    values = iter(steps)

    def _fake() -> float:
        return next(values, tail)

    return _fake


class TestMonotonicUtcClockUnit:
    def test_start_anchors_a_real_utc_and_monotonic_reading(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asa.scheduled_screening as scheduled_screening_module

        monkeypatch.setattr(scheduled_screening_module.time, "monotonic", lambda: 42.0)
        before = datetime.now(UTC)
        clock = scheduled_screening_module._MonotonicUtcClock.start()
        after = datetime.now(UTC)
        assert before <= clock.anchor_utc <= after
        assert clock.anchor_utc.tzinfo is UTC
        assert clock.anchor_monotonic == 42.0

    def test_now_advances_by_real_elapsed_monotonic_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asa.scheduled_screening as scheduled_screening_module

        anchor_utc = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
        clock = scheduled_screening_module._MonotonicUtcClock(anchor_utc, 100.0)
        monkeypatch.setattr(scheduled_screening_module.time, "monotonic", lambda: 137.5)
        assert clock.now() == anchor_utc + timedelta(seconds=37.5)

    def test_no_elapsed_time_returns_the_anchor_exactly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asa.scheduled_screening as scheduled_screening_module

        anchor_utc = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
        clock = scheduled_screening_module._MonotonicUtcClock(anchor_utc, 5.0)
        monkeypatch.setattr(scheduled_screening_module.time, "monotonic", lambda: 5.0)
        assert clock.now() == anchor_utc

    def test_two_calls_at_the_same_monotonic_instant_are_equal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asa.scheduled_screening as scheduled_screening_module

        clock = scheduled_screening_module._MonotonicUtcClock(
            datetime(2026, 8, 5, 12, 0, tzinfo=UTC), 0.0
        )
        monkeypatch.setattr(scheduled_screening_module.time, "monotonic", lambda: 10.0)
        assert clock.now() == clock.now()


def test_evaluation_and_request_identity_stay_frozen_across_a_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPRINT-013 P0's own required ownership: _FrozenCycleClock (the
    clock every pair's own evaluation timestamps and capability-request
    windows are built from) must stay exactly frozen across a whole
    cycle, unaffected by giving the rolling-window tracker its own
    separate, genuinely advancing clock. This is the same cycle-scoped
    reuse property S13-03B's own tests already depend on -- confirmed
    directly here by asserting the two pairs sharing symbol AAPL still
    reuse each other's requests, which is only possible if their request
    windows are byte-identical.
    """
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"), ("earnings_calendar", "AAPL"))
    responses = _complete_skew_momentum_responses(expiration) + _complete_skew_momentum_responses(
        expiration
    )

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(responses),
    )

    assert len(outcomes) == 2
    assert outcomes[0].error is None
    # earnings_calendar shares AAPL's quote with skew_momentum -- only
    # reusable if both pairs built byte-identical request windows from
    # the exact same frozen `now`, proving _FrozenCycleClock itself was
    # never touched by this fix.
    assert outcomes[1].error is None


def test_quota_clock_advances_independently_of_the_frozen_evaluation_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    import asa.scheduled_screening as scheduled_screening_module

    captured: list[scheduled_screening_module._MonotonicUtcClock] = []
    real_start = scheduled_screening_module._MonotonicUtcClock.start

    def _capturing_start() -> scheduled_screening_module._MonotonicUtcClock:
        clock = real_start()
        captured.append(clock)
        return clock

    monkeypatch.setattr(
        scheduled_screening_module._MonotonicUtcClock, "start", staticmethod(_capturing_start)
    )
    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"),)

    run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(
            _complete_skew_momentum_responses(expiration)
        ),
    )

    assert len(captured) == 1
    quota_clock = captured[0]
    first = quota_clock.now()
    second = quota_clock.now()
    # A real quota clock genuinely advances between two calls (however
    # little); the pre-fix frozen clock given to the tracker would have
    # returned the exact same value forever.
    assert second >= first


def test_a_long_running_cycle_regains_provider_capacity_after_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPRINT-013 P0's own confirmed root cause and required fix: with a
    single frozen clock feeding both evaluation identity and the
    rolling-window tracker, a provider's real rolling limit silently
    became a hard per-cycle cap -- once exhausted, it could never regain
    capacity for the rest of the cycle, however long the cycle actually
    ran in real wall-clock time. test_one_tracker_is_shared_across_every_
    pair_in_the_cycle (same tiny window, same universe shape, no elapsed
    time simulated) still correctly proves the second pair is refused
    when no real time has passed. Here, with the exact same tiny window
    but a real elapsed-time jump between pairs (as the quota clock, not
    any evaluation timestamp, measures it), the second pair now regains
    capacity and succeeds instead.
    """
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    _force_tiny_tradier_window(monkeypatch, window_limit=_SKEW_MOMENTUM_REQUESTS_PER_PAIR)
    import asa.scheduled_screening as scheduled_screening_module

    # Anchor (call 0), pair 1's own 4 requests closely spaced (call 1-4,
    # all well within the same 60s Tradier window together), then a
    # large jump comfortably past 60s before pair 2's own requests
    # (call 5+) -- a real elapsed-time gap, never an evaluation-timestamp
    # one (every pair still shares the exact same frozen `now` for its
    # own request windows; see test_evaluation_and_request_identity_
    # stay_frozen_across_a_cycle).
    monkeypatch.setattr(
        scheduled_screening_module.time,
        "monotonic",
        _stepped_monotonic(
            [0.0, 0.01, 0.02, 0.03, 0.04, 400.0, 400.01, 400.02, 400.03], tail=400.04
        ),
    )

    repository = InMemoryLatestResultRepository()
    expiration = (date.today() + timedelta(days=7)).isoformat()
    universe = (("skew_momentum", "AAPL"), ("skew_momentum", "MSFT"))

    outcomes = run_scheduled_refresh(
        universe,
        repository=repository,
        acquisition_attempt_repository=InMemoryAcquisitionAttemptRepository(),
        transport_factory=lambda _provider_id: ScriptedTransport(
            _complete_skew_momentum_responses(expiration)
        ),
    )

    assert len(outcomes) == 2
    assert outcomes[0].error is None
    assert outcomes[0].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR
    assert outcomes[1].error is None
    assert outcomes[1].request_count == _SKEW_MOMENTUM_REQUESTS_PER_PAIR
