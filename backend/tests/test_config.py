import json

import pytest
from pydantic import ValidationError

from asa.config import Settings


def test_deterministic_mode_requires_no_robinhood_secrets() -> None:
    settings = Settings(_env_file=None, broker_portfolio_provider="deterministic_fake_broker")
    assert settings.robinhood_username is None
    assert settings.robinhood_password is None


def test_robinhood_mode_fails_closed_without_credentials() -> None:
    with pytest.raises(ValidationError, match="requires username and password"):
        Settings(_env_file=None, broker_portfolio_provider="robinhood")


def test_robinhood_secrets_are_redacted_and_excluded_from_config_hash() -> None:
    first = Settings(
        _env_file=None,
        broker_portfolio_provider="robinhood",
        robinhood_username="private-user",
        robinhood_password="private-password",
        robinhood_totp_secret="private-totp",
        robinhood_account_numbers="one, two",
    )
    second = Settings(
        _env_file=None,
        broker_portfolio_provider="robinhood",
        robinhood_username="different-user",
        robinhood_password="different-password",
        robinhood_totp_secret="different-totp",
        robinhood_account_numbers="different-account",
    )

    representation = repr(first)
    assert "private-user" not in representation
    assert "private-password" not in representation
    assert "private-totp" not in representation
    assert first.effective_configuration_hash() == second.effective_configuration_hash()
    assert first.selected_robinhood_accounts == ("one", "two")


@pytest.mark.parametrize(
    ("provided", "expected"),
    [
        ("postgres://host/db", "postgresql+psycopg://host/db"),
        ("postgresql://host/db", "postgresql+psycopg://host/db"),
        (
            "postgresql://railway_user:railway_password@railway_host:5432/railway",
            "postgresql+psycopg://railway_user:railway_password@railway_host:5432/railway",
        ),
        ("postgresql+psycopg://host/db", "postgresql+psycopg://host/db"),
    ],
)
def test_railway_database_url_is_psycopg_compatible(provided: str, expected: str) -> None:
    assert Settings(_env_file=None, database_url=provided).database_url == expected


def test_database_url_strips_surrounding_whitespace() -> None:
    settings = Settings(_env_file=None, database_url="  postgresql://host/db  ")

    assert settings.database_url == "postgresql+psycopg://host/db"


@pytest.mark.parametrize(
    ("provided", "expected_error"),
    [
        ("  ", "Database URL cannot be empty"),
        ("${{Postgres.DATABASE_URL}}", "unresolved variable reference"),
        ("database.internal/asa", "must include a URL scheme"),
    ],
)
def test_invalid_database_url_fails_with_safe_actionable_error(
    provided: str,
    expected_error: str,
) -> None:
    with pytest.raises(ValidationError) as captured:
        Settings(_env_file=None, database_url=provided)

    message = str(captured.value)
    assert expected_error in message
    if provided.strip():
        assert provided.strip() not in message


def test_database_url_validation_never_discloses_url_components() -> None:
    sensitive_url = "private-user:private-password@private-host/private-database"

    with pytest.raises(ValidationError) as captured:
        Settings(_env_file=None, database_url=sensitive_url)

    message = str(captured.value)
    for sensitive_value in (
        sensitive_url,
        "private-user",
        "private-password",
        "private-host",
        "private-database",
    ):
        assert sensitive_value not in message


def test_railway_port_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9123")
    assert Settings(_env_file=None).port == 9123


def test_robinhood_provider_is_selected_from_railway_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from asa.bootstrap import DependencyOverrides, build_application
    from tests.fakes import InMemoryObservationRepository

    monkeypatch.setenv("ASA_BROKER_PORTFOLIO_PROVIDER", "robinhood")
    monkeypatch.setenv("ASA_ROBINHOOD_USERNAME", "railway-user")
    monkeypatch.setenv("ASA_ROBINHOOD_PASSWORD", "railway-password")
    application = build_application(
        Settings(_env_file=None),
        DependencyOverrides(repository=InMemoryObservationRepository()),
    )

    assert application.state.dependencies["broker_provider"].name == "robinhood"


def test_openapi_has_no_robinhood_secret_fields() -> None:
    from asa.bootstrap import DependencyOverrides, build_application
    from tests.fakes import InMemoryObservationRepository

    schema = json.dumps(
        build_application(
            Settings(_env_file=None),
            DependencyOverrides(repository=InMemoryObservationRepository()),
        ).openapi()
    )
    for secret_name in ("username", "password", "totp", "session", "cookie", "token"):
        assert secret_name not in schema.lower()
