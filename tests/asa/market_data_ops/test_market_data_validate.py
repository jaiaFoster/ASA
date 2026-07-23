from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from asa.bootstrap import DependencyOverrides, build_application
from asa.config import Settings
from market_data.transport import ReadOnlyHttpResponse
from tests.asa.fakes import InMemoryObservationRepository
from tests.asa.market_data_ops.fakes import ScriptedTransport


def _client(
    operations_token: str | None,
    transport_factory=None,
    **env: str,
) -> TestClient:
    return TestClient(
        build_application(
            Settings(operations_token=operations_token, **env),
            DependencyOverrides(
                repository=InMemoryObservationRepository(),
                market_data_transport_factory=transport_factory,
            ),
        )
    )


# --- endpoint_authentication_tests / missing_token_tests -----------------------------


def test_missing_authorization_header_returns_generic_404() -> None:
    client = _client("correct-token")
    response = client.post("/ops/market-data/validate", json={})
    assert response.status_code == 404


def test_operations_token_not_configured_returns_generic_404_even_with_header() -> None:
    client = _client(None)
    response = client.post(
        "/ops/market-data/validate",
        json={},
        headers={"Authorization": "Bearer anything"},
    )
    assert response.status_code == 404


# --- invalid_token_tests --------------------------------------------------------------


def test_invalid_token_returns_generic_404() -> None:
    client = _client("correct-token")
    response = client.post(
        "/ops/market-data/validate",
        json={},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 404


def test_malformed_authorization_scheme_returns_generic_404() -> None:
    client = _client("correct-token")
    response = client.post(
        "/ops/market-data/validate",
        json={},
        headers={"Authorization": "Basic correct-token"},
    )
    assert response.status_code == 404


def test_valid_token_with_no_live_credentials_is_accepted_and_blocked_closed() -> None:
    client = _client("correct-token")
    response = client.post(
        "/ops/market-data/validate",
        json={},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert {provider["provider"] for provider in body["providers"]} == {
        "tradier",
        "finnhub",
        "alpha_vantage",
    }
    assert all(
        provider["configuration_status"] == "disabled_missing_credentials"
        for provider in body["providers"]
    )
    assert all(provider["checks"] == [] for provider in body["providers"])
    assert response.text.count("correct-token") == 0


# --- dry_run_tests -----------------------------------------------------------------


def _raise_if_called(_provider_id: str) -> None:
    raise AssertionError("dry_run must never construct a live transport")


def test_tradier_option_chain_live_run_completes_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for POST-005B-LIVE-VALIDATION Phase 4: the fixed OPTION_CHAIN_V1
    validation subject previously carried no "expiration" projection, so Tradier's
    endpoint routing raised DomainInvariantError before any transport call, crashing
    the whole request with a raw 500. This exercises the full live (non-dry-run) path
    for all three of Tradier's capabilities, in the sorted order TradierProvider
    processes them (historical_bars_v1, option_chain_v1, real_time_quote_v1).
    """
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    option_row = {
        "symbol": "AAPL260821C00210000",
        "underlying": "AAPL",
        "expiration_date": "2026-08-21",
        "strike": "210",
        "option_type": "call",
        "bid": "4.9",
        "ask": "5.1",
        "last": "5",
        "volume": 1000,
        "open_interest": 5000,
        "greeks": {"delta": "0.5", "gamma": "0.03", "theta": "-0.1", "vega": "0.2", "rho": "0.01"},
    }
    responses = [
        ReadOnlyHttpResponse(
            200,
            {
                "history": {
                    "day": [
                        {
                            "date": "2026-07-20",
                            "open": "205.00",
                            "high": "212",
                            "low": "204",
                            "close": "210",
                            "volume": 50000000,
                        }
                    ]
                }
            },
            (),
            12,
            "tradier-request-1",
        ),
        ReadOnlyHttpResponse(
            200, {"options": {"option": [option_row]}}, (), 12, "tradier-request-2"
        ),
        ReadOnlyHttpResponse(
            200,
            {
                "quotes": {
                    "quote": {
                        "symbol": "AAPL",
                        "bid": "189.10",
                        "ask": "189.20",
                        "last": "189.15",
                        "bidsize": 1,
                        "asksize": 1,
                        "volume": 100,
                    }
                }
            },
            (),
            12,
            "tradier-request-3",
        ),
    ]
    client = _client(
        "correct-token", transport_factory=lambda _provider_id: ScriptedTransport(responses)
    )
    result = client.post(
        "/ops/market-data/validate",
        json={"providers": ["tradier"], "dry_run": False},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert result.status_code == 200
    body = result.json()
    (provider,) = body["providers"]
    assert provider["configuration_status"] == "enabled"
    checks_by_capability = {check["capability"]: check for check in provider["checks"]}
    assert set(checks_by_capability) == {
        "historical_bars_v1",
        "option_chain_v1",
        "real_time_quote_v1",
    }
    for check in checks_by_capability.values():
        assert check["normalized_check_status"] == "pass"
        assert check["diagnostic_detail_code"] == "VALID_DATA"


def test_dry_run_with_enabled_provider_never_calls_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "sandbox-secret-token")
    client = _client("correct-token", transport_factory=_raise_if_called)
    response = client.post(
        "/ops/market-data/validate",
        json={"providers": ["tradier"], "dry_run": True},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "dry_run"
    assert body["dry_run"] is True
    (provider,) = body["providers"]
    assert provider["provider"] == "tradier"
    assert provider["configuration_status"] == "enabled"
    assert all(check["normalized_check_status"] == "dry_run" for check in provider["checks"])
    assert all(check["request_count"] == 0 for check in provider["checks"])
    assert "sandbox-secret-token" not in response.text


# --- rate_limit_environment_tests -----------------------------------------------------


def test_non_development_environment_is_capped_at_fifty_runs_per_hour() -> None:
    client = _client("correct-token", environment="production")
    for _ in range(50):
        response = client.post(
            "/ops/market-data/validate",
            json={},
            headers={"Authorization": "Bearer correct-token"},
        )
        assert response.status_code == 200
    limited = client.post(
        "/ops/market-data/validate",
        json={},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert limited.status_code == 429


def test_development_environment_has_no_hourly_run_cap() -> None:
    client = _client("correct-token", environment="development")
    for _ in range(60):
        response = client.post(
            "/ops/market-data/validate",
            json={},
            headers={"Authorization": "Bearer correct-token"},
        )
        assert response.status_code == 200


# --- environment_configuration_error_tests --------------------------------------------


def test_invalid_environment_configuration_fails_closed_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_market_data_config_from_environment() raises ConfigurationError for an
    invalid ASA_TRADIER_ENV value; the endpoint must classify this per-provider
    rather than propagate an unhandled 500, for both dry_run and live requests.
    """
    monkeypatch.setenv("ASA_TRADIER_ENV", "not-a-real-environment")
    client = _client("correct-token")
    response = client.post(
        "/ops/market-data/validate",
        json={"dry_run": True},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "failed"
    assert {provider["provider"] for provider in body["providers"]} == {
        "tradier",
        "finnhub",
        "alpha_vantage",
    }
    assert all(
        provider["configuration_status"] == "configuration_error"
        for provider in body["providers"]
    )
    for provider in body["providers"]:
        (check,) = provider["checks"]
        assert check["normalized_check_status"] == "fail"
        assert check["diagnostic_detail_code"] == "CONFIGURATION_ERROR"
        assert check["request_count"] == 0
    assert "not-a-real-environment" not in response.text


# --- provider_selection_tests --------------------------------------------------------


def test_provider_selection_returns_only_requested_provider() -> None:
    client = _client("correct-token")
    response = client.post(
        "/ops/market-data/validate",
        json={"providers": ["finnhub"]},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert [provider["provider"] for provider in body["providers"]] == ["finnhub"]


def test_unsupported_provider_is_rejected() -> None:
    client = _client("correct-token")
    response = client.post(
        "/ops/market-data/validate",
        json={"providers": ["robinhood"]},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert response.status_code == 422


# --- secret_redaction_tests ------------------------------------------------------------


def test_redact_diagnostic_text_strips_bearer_tokens_and_urls() -> None:
    from market_data.validation import redact_diagnostic_text

    raw = (
        "request to https://api.tradier.com/v1/markets/quotes?token=abc failed: "
        "Authorization: Bearer sk-live-12345 was rejected"
    )
    redacted = redact_diagnostic_text(raw)
    assert "sk-live-12345" not in redacted
    assert "https://api.tradier.com" not in redacted
    assert "[REDACTED]" in redacted


def test_configuration_error_summary_is_redacted_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from asa.market_data_ops import service

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise service.ProviderFactoryError(
            "Provider 'tradier' rejected Authorization: Bearer super-secret-value"
        )

    monkeypatch.setattr(service, "_execute_live", _boom)
    monkeypatch.setenv("ASA_TRADIER_ENABLED", "true")
    monkeypatch.setenv("ASA_TRADIER_ACCESS_TOKEN", "super-secret-value")
    client = _client("correct-token")
    response = client.post(
        "/ops/market-data/validate",
        json={"providers": ["tradier"]},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert response.status_code == 200
    assert "super-secret-value" not in response.text


# --- request_budget_tests ------------------------------------------------------------


def test_budget_policy_never_exceeds_the_authorized_validation_ceiling() -> None:
    from asa.market_data_ops.service import _budget_policy_for
    from market_data.config import load_market_data_config

    config = load_market_data_config(
        {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "x"}
    )
    tradier_config = next(item for item in config.providers if item.provider_id == "tradier")
    policy = _budget_policy_for("tradier", tradier_config)
    assert policy.maximum_request_units <= 12
    assert policy.maximum_retries_per_request <= 1


def test_request_budget_manager_refuses_requests_beyond_the_authorized_ceiling() -> None:

    from asa.market_data_ops.service import Clock, _budget_policy_for
    from domain import MarketCapability
    from market_data.budget import BudgetExhaustedError, RequestBudgetManager
    from market_data.config import load_market_data_config

    config = load_market_data_config(
        {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "x"}
    )
    tradier_config = next(item for item in config.providers if item.provider_id == "tradier")
    policy = _budget_policy_for("tradier", tradier_config)
    manager = RequestBudgetManager((policy,), Clock())
    for _ in range(policy.maximum_request_units):
        manager.authorize("tradier", MarketCapability.REAL_TIME_QUOTE_V1, 1)
    with pytest.raises(BudgetExhaustedError):
        manager.authorize("tradier", MarketCapability.REAL_TIME_QUOTE_V1, 1)


# --- network_free_regression_suite (this whole module is network-free) --------------


def test_scripted_transport_fake_is_available_for_future_full_live_simulation() -> None:
    from market_data.transport import ReadOnlyHttpRequest

    transport = ScriptedTransport([])
    assert transport.requests == []
    with pytest.raises(IndexError):
        transport.get(ReadOnlyHttpRequest("production", "quotes", "/v1/markets/quotes", (), (), 10))
