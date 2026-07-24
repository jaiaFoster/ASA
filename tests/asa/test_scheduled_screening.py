"""SPRINT-008D/PROD-002: scheduled production screening execution."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from asa.scheduled_screening import (
    PRODUCTION_SCREENING_UNIVERSE,
    run_scheduled_refresh,
)
from market_data.transport import ReadOnlyHttpResponse
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


def test_production_universe_is_forward_factor_and_skew_momentum_only() -> None:
    signal_ids = {signal_id for signal_id, _symbol in PRODUCTION_SCREENING_UNIVERSE}
    assert signal_ids == {"forward_factor", "skew_momentum"}
    assert len(PRODUCTION_SCREENING_UNIVERSE) == 12
    assert len(set(PRODUCTION_SCREENING_UNIVERSE)) == 12  # no duplicate pairs


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
