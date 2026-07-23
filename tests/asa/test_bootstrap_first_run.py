"""SPRINT-008D/ACT-002: first-run validation from a genuinely empty deployment.

Exercises docs/api/agent-api-bootstrap.md's own four steps in order, against a
repository seeded with nothing at all -- not the handful of pre-existing
records tests/asa/test_ai_agent_workflow.py (SPRINT-008/API-005) seeds. That
test validates an agent working with an *established* deployment; this one
validates the very first session a brand-new deployment can support.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from market_data.transport import ReadOnlyHttpResponse
from tests.asa.fakes import InMemoryScreeningStateRepository
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


def _fresh_deployment_client() -> TestClient:
    """A deployment that has run every migration but never screened anything --
    the exact state docs/api/agent-api-bootstrap.md's "before you start" section
    describes."""
    expiration = (date.today() + timedelta(days=7)).isoformat()
    responses = _tradier_refresh_responses(expiration)
    return TestClient(
        build_application(
            Settings(agent_api_token=SecretStr("correct-token"), _env_file=None),
            DependencyOverrides(
                screening_state_repository=InMemoryScreeningStateRepository(),
                market_data_transport_factory=lambda _provider_id: ScriptedTransport(responses),
            ),
        )
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer correct-token"}


def test_bootstrap_first_run_from_a_genuinely_empty_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    client = _fresh_deployment_client()

    # Step 1: discover capabilities -- always available, even with zero data.
    capabilities = client.get("/api/v1/capabilities", headers=_auth())
    assert capabilities.status_code == 200
    signal_ids = {item["signal_id"] for item in capabilities.json()["signals"]}
    assert signal_ids == {"earnings_calendar", "forward_factor", "skew_momentum"}

    # Step 2: confirm the empty state is 200 + empty list, never 404.
    empty_list = client.get("/api/v1/screening", headers=_auth())
    assert empty_list.status_code == 200
    assert empty_list.json() == {"results": [], "total": 0, "limit": 100, "offset": 0}

    # A specific pair that has never been refreshed still 404s, distinguishably.
    no_result_yet = client.get("/api/v1/screening/skew_momentum/AAPL", headers=_auth())
    assert no_result_yet.status_code == 404
    assert no_result_yet.json()["detail"]["error_code"] == "NO_SCREENING_RESULT"

    # Step 3: produce the first real result.
    refresh = client.post("/api/v1/screening/skew_momentum/AAPL/refresh", headers=_auth())
    assert refresh.status_code == 200
    assert refresh.json()["symbol"] == "AAPL"
    assert refresh.json()["request_count"] >= 1

    # Step 4: the first result is now visible both individually and in the list.
    single = client.get("/api/v1/screening/skew_momentum/AAPL", headers=_auth())
    assert single.status_code == 200
    assert single.json()["signal_id"] == "skew_momentum"

    listed = client.get("/api/v1/screening", headers=_auth())
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
