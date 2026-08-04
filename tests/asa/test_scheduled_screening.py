"""SPRINT-008D/PROD-002: scheduled production screening execution."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from asa.scheduled_screening import (
    PRODUCTION_SCREENING_UNIVERSE,
    run_scheduled_refresh,
)
from market_data.attempts import AttemptQuery, InMemoryAcquisitionAttemptRepository
from market_data.transport import ReadOnlyHttpResponse
from screening import APPROVED_LIVE_UNIVERSE, EARNINGS_CALENDAR_UNIVERSE
from tests.asa.fakes import InMemoryLatestResultRepository
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


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
