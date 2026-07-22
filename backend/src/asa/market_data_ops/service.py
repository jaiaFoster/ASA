"""Bounded live Market Data validation, composed strictly from existing market_data
components (config loader, provider factory, request budget manager, provider
registry/validation types, diagnostic redaction). No provider or validation logic is
reimplemented here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from asa.market_data_ops.subjects import PROVIDER_CAPABILITIES, build_validation_subject
from asa.market_data_ops.transport import build_transport_for_provider
from domain import MarketCapability
from market_data.alpha_vantage import alpha_vantage_provider_registration
from market_data.budget import BudgetScope, RequestBudgetManager, RequestBudgetPolicy
from market_data.config import (
    ConfigurationError,
    ProviderConfig,
    load_market_data_config_from_environment,
)
from market_data.factory import ProviderDependencies, ProviderFactory, ProviderFactoryError
from market_data.finnhub import finnhub_provider_registration
from market_data.providers import ProviderValidationPlan, ValidationCheckStatus
from market_data.registry import ProviderRegistry
from market_data.tradier import tradier_provider_registration
from market_data.validation import redact_diagnostic_text

ALLOWED_PROVIDER_IDS = ("tradier", "finnhub", "alpha_vantage")

_ENTITLEMENT_BLOCKED_CODES = {"AUTHORIZATION_FAILED", "ENTITLEMENT_MISSING"}
_SCHEMA_INVALID_CODES = {"SCHEMA_MISMATCH", "EMPTY_PAYLOAD"}
_FRESHNESS_STALE_CODES = {"STALE_DATA"}


@dataclass(frozen=True, slots=True)
class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CapabilityCheckResult:
    provider_id: str
    capability: MarketCapability
    normalized_check_status: str
    diagnostic_detail_code: str
    request_count: int
    latency_milliseconds: int | None
    entitlement_status: str
    schema_status: str
    freshness_status: str
    quota_metadata_when_safe: dict[str, str] | None
    redacted_failure_summary: str | None


@dataclass(frozen=True, slots=True)
class ProviderCheckResult:
    provider_id: str
    configuration_status: str
    checks: tuple[CapabilityCheckResult, ...]


@dataclass(frozen=True, slots=True)
class ValidationRunOutcome:
    overall_status: str
    dry_run: bool
    generated_at: datetime
    providers: tuple[ProviderCheckResult, ...]


def _provider_factory() -> ProviderFactory:
    return ProviderFactory(
        (
            tradier_provider_registration(),
            finnhub_provider_registration(),
            alpha_vantage_provider_registration(),
        )
    )


def _classify(detail_code: str) -> tuple[str, str, str]:
    entitlement = "blocked" if detail_code in _ENTITLEMENT_BLOCKED_CODES else "unknown"
    if detail_code == "VALID_DATA":
        entitlement = "known"
    schema = "invalid" if detail_code in _SCHEMA_INVALID_CODES else "inconclusive"
    if detail_code == "VALID_DATA":
        schema = "valid"
    freshness = "stale" if detail_code in _FRESHNESS_STALE_CODES else "unknown"
    if detail_code == "VALID_DATA":
        freshness = "fresh"
    return entitlement, schema, freshness


def _quota_metadata_for(attempts: tuple[object, ...]) -> dict[str, str] | None:
    for attempt in reversed(attempts):
        response = getattr(attempt, "response", None)
        if response is not None and response.quota_metadata:
            return dict(response.quota_metadata)
    return None


def _latency_for(attempts: tuple[object, ...]) -> int | None:
    for attempt in reversed(attempts):
        response = getattr(attempt, "response", None)
        if response is not None:
            return int(response.latency_milliseconds)
    return None


def run_bounded_validation(
    *,
    requested_provider_ids: tuple[str, ...],
    dry_run: bool,
    transport_factory: Callable[[str], object] = build_transport_for_provider,
) -> ValidationRunOutcome:
    config = load_market_data_config_from_environment()
    configs_by_id = {item.provider_id: item for item in config.providers}
    clock = Clock()
    factory = _provider_factory()

    provider_results: list[ProviderCheckResult] = []
    for provider_id in requested_provider_ids:
        provider_config = configs_by_id.get(provider_id)
        if provider_config is None or not provider_config.enabled:
            provider_results.append(
                ProviderCheckResult(provider_id, "disabled_missing_credentials", ())
            )
            continue
        capabilities = PROVIDER_CAPABILITIES[provider_id]
        if dry_run:
            checks = tuple(
                CapabilityCheckResult(
                    provider_id,
                    capability,
                    "dry_run",
                    "DRY_RUN_NOT_EXECUTED",
                    0,
                    None,
                    "unknown",
                    "inconclusive",
                    "unknown",
                    None,
                    None,
                )
                for capability in capabilities
            )
            provider_results.append(ProviderCheckResult(provider_id, "enabled", checks))
            continue
        try:
            checks = _execute_live(
                provider_id, provider_config, capabilities, factory, clock, transport_factory
            )
        except (ProviderFactoryError, ConfigurationError) as exc:
            checks = (
                CapabilityCheckResult(
                    provider_id,
                    capabilities[0],
                    "fail",
                    "CONFIGURATION_ERROR",
                    0,
                    None,
                    "unknown",
                    "inconclusive",
                    "unknown",
                    None,
                    redact_diagnostic_text(str(exc)),
                ),
            )
        provider_results.append(ProviderCheckResult(provider_id, "enabled", checks))

    statuses = {
        check.normalized_check_status
        for provider in provider_results
        for check in provider.checks
    }
    if dry_run:
        overall = "dry_run"
    elif not any(provider.checks for provider in provider_results):
        overall = "failed"
    elif "fail" in statuses:
        overall = "failed" if statuses <= {"fail"} else "partial"
    else:
        overall = "passed"

    return ValidationRunOutcome(overall, dry_run, clock.now(), tuple(provider_results))


def _budget_policy_for(provider_id: str, provider_config: ProviderConfig) -> RequestBudgetPolicy:
    """The ceiling enforced here is always the provider's own validation_budget --
    ValidationBudgetConfig.__post_init__ already refuses more than the authorized safety
    ceiling (<=12 requests/run, <=3/capability, <=1 retry); this never widens it.
    """
    return RequestBudgetPolicy(
        provider_id,
        BudgetScope.RUNTIME,
        provider_config.validation_budget.max_requests_per_provider_run,
        1,
        provider_config.validation_budget.max_retries_per_request,
        "ops-validation-v1",
    )


def _execute_live(
    provider_id: str,
    provider_config: ProviderConfig,
    capabilities: tuple[MarketCapability, ...],
    factory: ProviderFactory,
    clock: Clock,
    transport_factory: Callable[[str], object],
) -> tuple[CapabilityCheckResult, ...]:
    policy = _budget_policy_for(provider_id, provider_config)
    budget_manager = RequestBudgetManager((policy,), clock)
    dependencies = ProviderDependencies(transport_factory(provider_id), clock, budget_manager)
    provider = factory.create(provider_config, dependencies)
    registry = ProviderRegistry((provider,))
    as_of = clock.now()
    subjects = tuple(
        build_validation_subject(provider_id, capability, as_of=as_of)
        for capability in capabilities
    )
    maximum = min(
        provider_config.validation_budget.max_requests_per_provider_run,
        len(capabilities) * provider_config.validation_budget.max_requests_per_capability_check,
    )
    plan = ProviderValidationPlan(
        f"ops-validate:{provider_id}:{provider_config.adapter_version}",
        provider_id,
        capabilities,
        maximum,
        maximum,
        provider_config.validation_budget.timeout_seconds,
        subjects,
    )
    (report,) = registry.validate((plan,))
    results = []
    for check in report.checks:
        attempts = tuple(
            attempt for attempt in report.attempts if attempt.capability.value == check.check_id
        )
        entitlement, schema, freshness = _classify(check.detail_code)
        normalized_status = {
            ValidationCheckStatus.PASS: "pass",
            ValidationCheckStatus.FAIL: "fail",
            ValidationCheckStatus.SKIPPED: "skipped",
            ValidationCheckStatus.NOT_SUPPORTED: "not_supported",
        }[check.status]
        results.append(
            CapabilityCheckResult(
                provider_id,
                MarketCapability(check.check_id),
                normalized_status,
                check.detail_code,
                len(attempts),
                _latency_for(attempts),
                entitlement,
                schema,
                freshness,
                _quota_metadata_for(attempts),
                None if check.status is ValidationCheckStatus.PASS
                else redact_diagnostic_text(check.safe_summary),
            )
        )
    return tuple(results)
