from __future__ import annotations

import dataclasses

import pytest

from market_data.config import (
    ConfigurationError,
    ProviderEndpointEnvironment,
    SecretValue,
    load_market_data_config,
)


def by_id(config: object, provider_id: str) -> object:
    return next(value for value in config.providers if value.provider_id == provider_id)  # type: ignore[attr-defined]


def test_offline_configuration_requires_no_live_credentials() -> None:
    config = load_market_data_config({})
    fixture = by_id(config, "deterministic_fixture")
    assert fixture.enabled  # type: ignore[attr-defined]
    assert all(
        not value.enabled
        for value in config.providers
        if value.provider_id != "deterministic_fixture"
    )


def test_enabled_provider_requires_credential_before_network() -> None:
    with pytest.raises(ConfigurationError, match="requires its configured credential"):
        load_market_data_config({"ASA_FINNHUB_ENABLED": "true"})


def test_valid_configuration_is_immutable_and_explicit() -> None:
    config = load_market_data_config(
        {
            "ASA_TRADIER_ENABLED": "true",
            "ASA_TRADIER_ACCESS_TOKEN": "tradier-secret",
            "ASA_TRADIER_ENV": "sandbox",
            "ASA_FINNHUB_ENABLED": "true",
            "ASA_FINNHUB_API_KEY": "finnhub-secret",
        }
    )
    tradier = by_id(config, "tradier")
    assert tradier.endpoint_environment is ProviderEndpointEnvironment.SANDBOX  # type: ignore[attr-defined]
    assert tradier.credential.reveal() == "tradier-secret"  # type: ignore[attr-defined]
    with pytest.raises(dataclasses.FrozenInstanceError):
        tradier.enabled = False  # type: ignore[attr-defined,misc]


def test_secrets_never_enter_repr_str_or_safe_hash() -> None:
    secret = SecretValue("top-secret-value")
    config = load_market_data_config(
        {"ASA_FINNHUB_ENABLED": "true", "ASA_FINNHUB_API_KEY": secret.reveal()}
    )
    rendered = f"{config!r} {secret!r} {secret!s} {config.safe_identity}"
    assert "top-secret-value" not in rendered
    assert "[REDACTED]" in rendered


def test_compatibility_alias_is_centralized_and_secret_free() -> None:
    config = load_market_data_config(
        {"ASA_FINNHUB_ENABLED": "true", "FINNHUB_API_KEY": "legacy-secret"}
    )
    assert config.compatibility_diagnostics == (
        "FINNHUB_API_KEY is deprecated; use ASA_FINNHUB_API_KEY",
    )
    assert "legacy-secret" not in repr(config)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"ASA_TRADIER_ENV": "invalid"}, "sandbox or production"),
        ({"ASA_FINNHUB_ENABLED": "maybe"}, "must be boolean"),
        ({"ASA_FINNHUB_TIMEOUT_SECONDS": "slow"}, "must be an integer"),
        ({"ASA_FINNHUB_TIMEOUT_SECONDS": "0"}, "positive integer"),
        ({"ASA_FINNHUB_MAX_REQUESTS_PER_RUN": "0"}, "positive integer"),
        (
            {"ASA_FINNHUB_MAX_REQUESTS_PER_RUN": "1", "ASA_FINNHUB_BURST_LIMIT": "2"},
            "cannot exceed request budget",
        ),
    ],
)
def test_malformed_configuration_fails_actionably(
    values: dict[str, str], message: str
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        load_market_data_config(values)
