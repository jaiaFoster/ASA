"""Bounded, opt-in Provider validation orchestration (MD-008)."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from domain import MarketCapability
from domain.values import DomainInvariantError
from market_data.config import ProviderConfig
from market_data.providers import (
    ProviderValidationPlan,
    ProviderValidationReport,
    ValidationCheckStatus,
)
from market_data.registry import ProviderRegistry


class ValidationOverallStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    DRY_RUN = "dry_run"


class DiagnosticFinding(str, Enum):
    LIKELY_CONFIGURATION_ISSUE = "likely_configuration_issue"
    LIKELY_AUTHENTICATION_ISSUE = "likely_authentication_issue"
    LIKELY_ENTITLEMENT_ISSUE = "likely_entitlement_issue"
    LIKELY_REQUEST_PARAMETER_ISSUE = "likely_request_parameter_issue"
    LIKELY_SYMBOL_ISSUE = "likely_symbol_issue"
    LIKELY_TIME_RANGE_ISSUE = "likely_time_range_issue"
    LIKELY_RESOLUTION_ISSUE = "likely_resolution_issue"
    PROVIDER_RETURNED_NO_DATA = "provider_returned_no_data"
    PROVIDER_RETURNED_EMPTY_PAYLOAD = "provider_returned_empty_payload"
    PROVIDER_SCHEMA_CHANGED = "provider_schema_changed"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    LOCAL_TRANSPORT_ISSUE = "local_transport_issue"
    UNKNOWN_ISSUE = "unknown_issue"


@dataclass(frozen=True, slots=True)
class ValidationRequest:
    provider_ids: tuple[str, ...]
    capabilities: tuple[MarketCapability, ...] = ()
    dry_run: bool = True
    allow_live: bool = False

    def __post_init__(self) -> None:
        providers = tuple(sorted(set(self.provider_ids)))
        capabilities = tuple(sorted(set(self.capabilities), key=lambda item: item.value))
        if not providers or any(not item or item != item.strip() for item in providers):
            raise DomainInvariantError("ValidationRequest requires normalized provider IDs")
        object.__setattr__(self, "provider_ids", providers)
        object.__setattr__(self, "capabilities", capabilities)


@dataclass(frozen=True, slots=True)
class ValidationRequestPlan:
    plans: tuple[ProviderValidationPlan, ...]
    total_request_ceiling: int
    live_providers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidationRunResult:
    request_plan: ValidationRequestPlan
    reports: tuple[ProviderValidationReport, ...]
    overall_status: ValidationOverallStatus

    @property
    def exit_code(self) -> int:
        return (
            0
            if self.overall_status
            in {ValidationOverallStatus.PASSED, ValidationOverallStatus.DRY_RUN}
            else 1
        )


class ProviderValidationRunner:
    """Build and execute immutable plans without bypassing configured ceilings."""

    def __init__(
        self, registry: ProviderRegistry, provider_configs: tuple[ProviderConfig, ...]
    ) -> None:
        self._registry = registry
        self._configs = {item.provider_id: item for item in provider_configs}

    def plan(self, request: ValidationRequest) -> ValidationRequestPlan:
        plans: list[ProviderValidationPlan] = []
        live: list[str] = []
        for provider_id in request.provider_ids:
            provider = self._registry.provider(provider_id)
            config = self._configs.get(provider_id)
            if config is None:
                raise DomainInvariantError(
                    f"Provider {provider_id!r} lacks validation configuration"
                )
            capabilities = request.capabilities or provider.capabilities
            maximum = min(
                config.validation_budget.max_requests_per_provider_run,
                len(capabilities) * config.validation_budget.max_requests_per_capability_check,
            )
            plans.append(
                ProviderValidationPlan(
                    f"validate:{provider_id}:{config.adapter_version}",
                    provider_id,
                    capabilities,
                    maximum,
                    maximum,
                    config.validation_budget.timeout_seconds,
                )
            )
            if provider_id != "deterministic_fixture":
                live.append(provider_id)
        ordered = tuple(sorted(plans, key=lambda item: item.provider_id))
        return ValidationRequestPlan(
            ordered, sum(item.maximum_requests for item in ordered), tuple(sorted(live))
        )

    def run(self, request: ValidationRequest) -> ValidationRunResult:
        request_plan = self.plan(request)
        if request.dry_run:
            return ValidationRunResult(request_plan, (), ValidationOverallStatus.DRY_RUN)
        if request_plan.live_providers and not request.allow_live:
            raise DomainInvariantError("Live Provider validation requires explicit opt-in")
        reports = self._registry.validate(request_plan.plans)
        statuses = tuple(check.status for report in reports for check in report.checks)
        if any(status is ValidationCheckStatus.FAIL for status in statuses):
            overall = ValidationOverallStatus.FAILED
        elif any(
            status in {ValidationCheckStatus.SKIPPED, ValidationCheckStatus.NOT_SUPPORTED}
            for status in statuses
        ):
            overall = ValidationOverallStatus.PARTIAL
        else:
            overall = ValidationOverallStatus.PASSED
        return ValidationRunResult(request_plan, reports, overall)


_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)(token|password|api[_-]?key|authorization)\s*[=:]\s*\S+"),
    re.compile(r"https?://\S+"),
)


def redact_diagnostic_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def validation_result_to_data(result: ValidationRunResult) -> dict[str, object]:
    return {
        "overall_status": result.overall_status.value,
        "exit_code": result.exit_code,
        "request_plan": {
            "total_request_ceiling": result.request_plan.total_request_ceiling,
            "live_providers": list(result.request_plan.live_providers),
            "providers": [
                {
                    "provider_id": plan.provider_id,
                    "capabilities": [item.value for item in plan.capabilities],
                    "maximum_requests": plan.maximum_requests,
                    "maximum_request_units": plan.maximum_request_units,
                    "timeout_seconds": plan.timeout_seconds,
                }
                for plan in result.request_plan.plans
            ],
        },
        "reports": [
            {
                "provider_id": report.provider_id,
                "adapter_version": report.adapter_version,
                "checks": [
                    {
                        "check_id": check.check_id,
                        "status": check.status.value,
                        "detail_code": check.detail_code,
                        "safe_summary": redact_diagnostic_text(check.safe_summary),
                    }
                    for check in report.checks
                ],
            }
            for report in result.reports
        ],
    }


def render_validation_result(result: ValidationRunResult) -> str:
    return json.dumps(validation_result_to_data(result), sort_keys=True, indent=2)


def command_main(
    argv: Sequence[str], runner_factory: Callable[[], ProviderValidationRunner]
) -> int:
    parser = argparse.ArgumentParser(description="Run bounded Market Data Provider validation")
    parser.add_argument("--provider", action="append", required=True)
    parser.add_argument(
        "--capability", action="append", choices=[item.value for item in MarketCapability]
    )
    parser.add_argument(
        "--execute", action="store_true", help="execute instead of showing a dry-run plan"
    )
    parser.add_argument(
        "--allow-live", action="store_true", help="explicitly authorize bounded live checks"
    )
    args = parser.parse_args(tuple(argv))
    capabilities = tuple(MarketCapability(item) for item in (args.capability or ()))
    result = runner_factory().run(
        ValidationRequest(tuple(args.provider), capabilities, not args.execute, args.allow_live)
    )
    print(render_validation_result(result))
    return result.exit_code
