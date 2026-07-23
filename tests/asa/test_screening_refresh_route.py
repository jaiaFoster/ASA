"""API-004: POST /api/v1/screening/{signal}/{symbol}/refresh."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from market_data.transport import ReadOnlyHttpResponse
from tests.asa.fakes import InMemoryScreeningStateRepository
from tests.asa.market_data_ops.fakes import ScriptedTransport, tradier_quote_response


def _client(transport_factory: Callable[[str], object] | None = None) -> TestClient:
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr("correct-token"), _env_file=None),
            DependencyOverrides(
                screening_state_repository=InMemoryScreeningStateRepository(),
                market_data_transport_factory=transport_factory,
            ),
        )
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer correct-token"}


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
                            "symbol": "AAPL_TEST_CALL",
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


class TestAuthenticationAndValidation:
    def test_without_authorization_header_is_404(self) -> None:
        response = _client().post("/api/v1/screening/skew_momentum/AAPL/refresh")
        assert response.status_code == 404

    def test_unknown_signal_is_404(self) -> None:
        response = _client().post(
            "/api/v1/screening/not_a_real_signal/AAPL/refresh", headers=_auth()
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error_code"] == "UNKNOWN_SIGNAL"

    def test_symbol_outside_approved_live_universe_is_422(self) -> None:
        response = _client().post(
            "/api/v1/screening/skew_momentum/NOTREAL/refresh", headers=_auth()
        )
        assert response.status_code == 422
        assert response.json()["detail"]["error_code"] == "UNSUPPORTED_SYMBOL"

    def test_no_live_provider_configured_is_503(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No ASA_TRADIER_ENABLED/ASA_FINNHUB_ENABLED/ASA_ALPHA_VANTAGE_ENABLED set
        # -- every provider is disabled by default.
        for name in (
            "ASA_TRADIER_ENABLED",
            "ASA_FINNHUB_ENABLED",
            "ASA_ALPHA_VANTAGE_ENABLED",
        ):
            monkeypatch.delenv(name, raising=False)
        response = _client().post("/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth())
        assert response.status_code == 503
        assert response.json()["detail"]["error_code"] == "NO_LIVE_PROVIDER_CONFIGURED"


class TestSuccessfulRefresh:
    def test_refresh_persists_and_returns_a_result_with_request_accounting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        expiration = (date.today() + timedelta(days=7)).isoformat()
        responses = _tradier_refresh_responses(expiration)
        client = _client(transport_factory=lambda _provider_id: ScriptedTransport(responses))

        response = client.post("/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth())

        assert response.status_code == 200
        body = response.json()
        assert body["signal_id"] == "skew_momentum"
        assert body["symbol"] == "AAPL"
        assert body["request_count"] >= 1
        assert body["updated_at"] is not None
        assert body["age_seconds"] >= 0
        # "sandbox-secret-token" must never appear in the response.
        assert "sandbox-secret-token" not in response.text

    def test_refresh_result_is_then_visible_via_get(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
        monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
        expiration = (date.today() + timedelta(days=7)).isoformat()
        responses = _tradier_refresh_responses(expiration)
        client = _client(transport_factory=lambda _provider_id: ScriptedTransport(responses))

        client.post("/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth())
        follow_up = client.get("/api/v1/screening/skew_momentum/AAPL", headers=_auth())

        assert follow_up.status_code == 200
        assert follow_up.json()["symbol"] == "AAPL"
