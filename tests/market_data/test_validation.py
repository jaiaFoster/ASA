from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from domain import MarketCapability
from market_data import (
    DeterministicFixtureProvider,
    ProviderDependencies,
    ProviderFactory,
    ProviderRegistry,
    ProviderValidationRunner,
    RequestBudgetAuthorization,
    ValidationOverallStatus,
    ValidationRequest,
    command_main,
    fixture_provider_registration,
    load_market_data_config,
    redact_diagnostic_text,
    validation_result_to_data,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Clock:
    def now(self) -> datetime:
        return NOW


class NoBudgetCalls:
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        raise AssertionError("validation orchestration cannot bypass its plan")


def runner() -> ProviderValidationRunner:
    config = load_market_data_config({})
    provider_config = next(
        item for item in config.providers if item.provider_id == "deterministic_fixture"
    )
    provider = ProviderFactory((fixture_provider_registration(),)).create(
        provider_config, ProviderDependencies(object(), Clock(), NoBudgetCalls())
    )
    assert isinstance(provider, DeterministicFixtureProvider)
    return ProviderValidationRunner(ProviderRegistry((provider,)), config.providers)


def test_dry_run_exposes_bounded_request_plan_without_execution() -> None:
    result = runner().run(ValidationRequest(("deterministic_fixture",)))
    assert result.overall_status is ValidationOverallStatus.DRY_RUN
    assert result.reports == ()
    assert result.request_plan.total_request_ceiling == 12
    assert result.request_plan.live_providers == ()
    data = validation_result_to_data(result)
    assert data["request_plan"] == {
        "total_request_ceiling": 12,
        "live_providers": [],
        "providers": [
            {
                "provider_id": "deterministic_fixture",
                "capabilities": [
                    item.value
                    for item in sorted(provider_capabilities(), key=lambda item: item.value)
                ],
                "maximum_requests": 12,
                "maximum_request_units": 12,
                "timeout_seconds": 10,
            }
        ],
    }


def provider_capabilities() -> tuple[MarketCapability, ...]:
    return (
        MarketCapability.EARNINGS_CALENDAR_V1,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.OPTION_CHAIN_V1,
        MarketCapability.REAL_TIME_QUOTE_V1,
    )


def test_offline_fixture_validation_executes_and_reports_pass() -> None:
    result = runner().run(
        ValidationRequest(
            ("deterministic_fixture",),
            (MarketCapability.REAL_TIME_QUOTE_V1,),
            dry_run=False,
        )
    )
    assert result.overall_status is ValidationOverallStatus.PASSED
    assert result.exit_code == 0
    assert result.reports[0].checks[0].status.value == "pass"


def test_unsupported_capability_is_partial_not_a_new_check_status() -> None:
    result = runner().run(
        ValidationRequest(
            ("deterministic_fixture",),
            (MarketCapability.TRADING_CALENDAR_V1,),
            dry_run=False,
        )
    )
    assert result.overall_status is ValidationOverallStatus.PARTIAL
    assert result.exit_code == 1
    assert result.reports[0].checks[0].status.value == "not_supported"


@pytest.mark.parametrize(
    "value",
    (
        "Authorization: Bearer abc123",
        "api_key=supersecret",
        "token:secret-value",
        "https://user:pass@example.test/private",
    ),
)
def test_diagnostic_output_redacts_secret_like_values_and_urls(value: str) -> None:
    result = redact_diagnostic_text(value)
    assert "secret" not in result.lower()
    assert "abc123" not in result
    assert "example.test" not in result
    assert "[REDACTED]" in result


def test_command_defaults_to_dry_run_and_prints_machine_readable_plan(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = command_main(("--provider", "deterministic_fixture"), runner)
    output = capsys.readouterr().out
    assert code == 0
    assert '"overall_status": "dry_run"' in output
    assert '"total_request_ceiling": 12' in output


def test_validation_request_is_deterministically_normalized() -> None:
    request = ValidationRequest(
        ("deterministic_fixture", "deterministic_fixture"),
        (MarketCapability.REAL_TIME_QUOTE_V1, MarketCapability.REAL_TIME_QUOTE_V1),
    )
    assert request.provider_ids == ("deterministic_fixture",)
    assert request.capabilities == (MarketCapability.REAL_TIME_QUOTE_V1,)
