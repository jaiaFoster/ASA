"""Centralized, secret-safe Market Data provider configuration (MD-002)."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class ConfigurationError(ValueError):
    """Safe actionable configuration failure that never reproduces input values."""


class ProviderEndpointEnvironment(str, Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True, repr=False)
class SecretValue:
    """In-memory secret wrapper whose display representations are always redacted."""

    _value: str

    def __post_init__(self) -> None:
        if not self._value or self._value != self._value.strip():
            raise ConfigurationError("Provider credential must be non-empty normalized text")

    def __repr__(self) -> str:
        return "SecretValue('[REDACTED]')"

    def __str__(self) -> str:
        return "[REDACTED]"

    def reveal(self) -> str:
        """Return the value only to an explicitly constructed adapter dependency."""
        return self._value


@dataclass(frozen=True, slots=True)
class RequestBudgetConfig:
    max_requests_per_run: int = 100
    burst_limit: int = 1

    def __post_init__(self) -> None:
        _positive(self.max_requests_per_run, "max_requests_per_run")
        _positive(self.burst_limit, "burst_limit")
        if self.burst_limit > self.max_requests_per_run:
            raise ConfigurationError("Provider burst limit cannot exceed request budget")


@dataclass(frozen=True, slots=True)
class RetryConfig:
    max_retries: int = 1
    backoff_seconds: tuple[int, ...] = (1,)

    def __post_init__(self) -> None:
        if type(self.max_retries) is not int or self.max_retries < 0:
            raise ConfigurationError("Provider retry count must be a non-negative integer")
        if len(self.backoff_seconds) != self.max_retries:
            raise ConfigurationError("Provider backoff schedule must match retry count")
        if any(type(value) is not int or value < 0 for value in self.backoff_seconds):
            raise ConfigurationError("Provider backoff values must be non-negative integers")


@dataclass(frozen=True, slots=True)
class ValidationBudgetConfig:
    max_requests_per_provider_run: int = 12
    max_requests_per_capability_check: int = 3
    max_retries_per_request: int = 1
    timeout_seconds: int = 10
    concurrency_per_provider: int = 1

    def __post_init__(self) -> None:
        for name in (
            "max_requests_per_provider_run",
            "max_requests_per_capability_check",
            "timeout_seconds",
            "concurrency_per_provider",
        ):
            _positive(getattr(self, name), name)
        if type(self.max_retries_per_request) is not int or self.max_retries_per_request < 0:
            raise ConfigurationError("Validation retry count must be a non-negative integer")
        if self.max_requests_per_capability_check > self.max_requests_per_provider_run:
            raise ConfigurationError("Capability validation budget cannot exceed provider budget")
        if self.max_requests_per_provider_run > 12:
            raise ConfigurationError("Validation request budget exceeds the authorized safety ceiling")
        if self.max_requests_per_capability_check > 3:
            raise ConfigurationError("Capability request budget exceeds the authorized safety ceiling")
        if self.max_retries_per_request > 1:
            raise ConfigurationError("Validation retry budget exceeds the authorized safety ceiling")
        if self.timeout_seconds > 10:
            raise ConfigurationError("Validation timeout exceeds the authorized safety ceiling")
        if self.concurrency_per_provider != 1:
            raise ConfigurationError("Validation provider concurrency must equal one")


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_id: str
    adapter_type: str
    adapter_version: str
    enabled: bool
    endpoint_environment: ProviderEndpointEnvironment
    credential: SecretValue | None
    timeout_seconds: int
    request_budget: RequestBudgetConfig
    retry: RetryConfig
    validation_budget: ValidationBudgetConfig

    def __post_init__(self) -> None:
        for name in ("provider_id", "adapter_type", "adapter_version"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ConfigurationError(f"Provider {name} must be non-empty normalized text")
        if type(self.enabled) is not bool:
            raise ConfigurationError("Provider enabled flag must be boolean")
        _positive(self.timeout_seconds, "timeout_seconds")
        if self.timeout_seconds > 60:
            raise ConfigurationError("Provider timeout exceeds the configured safety ceiling")
        if self.enabled and self.provider_id != "deterministic_fixture" and self.credential is None:
            raise ConfigurationError(
                f"Enabled provider {self.provider_id!r} requires its configured credential"
            )

    @property
    def safe_identity(self) -> str:
        payload = {
            "adapter_type": self.adapter_type,
            "adapter_version": self.adapter_version,
            "enabled": self.enabled,
            "endpoint_environment": self.endpoint_environment.value,
            "provider_id": self.provider_id,
            "request_budget": {
                "burst_limit": self.request_budget.burst_limit,
                "max_requests_per_run": self.request_budget.max_requests_per_run,
            },
            "retry": {
                "backoff_seconds": self.retry.backoff_seconds,
                "max_retries": self.retry.max_retries,
            },
            "timeout_seconds": self.timeout_seconds,
            "validation_budget": {
                "concurrency_per_provider": self.validation_budget.concurrency_per_provider,
                "max_requests_per_capability_check": (
                    self.validation_budget.max_requests_per_capability_check
                ),
                "max_requests_per_provider_run": (
                    self.validation_budget.max_requests_per_provider_run
                ),
                "max_retries_per_request": self.validation_budget.max_retries_per_request,
                "timeout_seconds": self.validation_budget.timeout_seconds,
            },
            "credential_reference": f"{self.provider_id}:configured"
            if self.credential is not None
            else None,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class MarketDataConfig:
    providers: tuple[ProviderConfig, ...]
    compatibility_diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        providers = tuple(sorted(self.providers, key=lambda value: value.provider_id))
        ids = tuple(value.provider_id for value in providers)
        if len(ids) != len(set(ids)):
            raise ConfigurationError("Market Data providers must have unique identities")
        object.__setattr__(self, "providers", providers)
        object.__setattr__(
            self, "compatibility_diagnostics", tuple(sorted(set(self.compatibility_diagnostics)))
        )

    @property
    def safe_identity(self) -> str:
        encoded = json.dumps(
            [value.safe_identity for value in self.providers],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


def _positive(value: object, field_name: str) -> None:
    if type(value) is not int or cast_int(value) <= 0:
        raise ConfigurationError(f"Provider {field_name} must be a positive integer")


def cast_int(value: object) -> int:
    return value if type(value) is int else 0


def _integer(values: Mapping[str, str], name: str, default: int) -> int:
    raw = values.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"Provider configuration {name} must be an integer") from exc


def _boolean(values: Mapping[str, str], name: str, default: bool) -> bool:
    raw = values.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Provider configuration {name} must be boolean")


def _credential(
    values: Mapping[str, str],
    preferred: str,
    alias: str,
    diagnostics: list[str],
) -> SecretValue | None:
    preferred_value = values.get(preferred)
    alias_value = values.get(alias)
    if preferred_value is not None:
        return SecretValue(preferred_value.strip())
    if alias_value is not None:
        diagnostics.append(f"{alias} is deprecated; use {preferred}")
        return SecretValue(alias_value.strip())
    return None


def _provider(
    values: Mapping[str, str],
    provider_id: str,
    credential: SecretValue | None,
    *,
    default_enabled: bool = False,
    endpoint_environment: ProviderEndpointEnvironment = ProviderEndpointEnvironment.PRODUCTION,
) -> ProviderConfig:
    prefix = f"ASA_{provider_id.upper()}"
    enabled = _boolean(values, f"{prefix}_ENABLED", default_enabled)
    timeout = _integer(values, f"{prefix}_TIMEOUT_SECONDS", 10)
    requests = _integer(values, f"{prefix}_MAX_REQUESTS_PER_RUN", 100)
    burst = _integer(values, f"{prefix}_BURST_LIMIT", 1)
    retries = _integer(values, f"{prefix}_MAX_RETRIES", 1)
    return ProviderConfig(
        provider_id,
        provider_id,
        "v1",
        enabled,
        endpoint_environment,
        credential,
        timeout,
        RequestBudgetConfig(requests, burst),
        RetryConfig(retries, tuple(range(1, retries + 1))),
        ValidationBudgetConfig(),
    )


def load_market_data_config(values: Mapping[str, str]) -> MarketDataConfig:
    """Build complete immutable configuration from one explicit environment mapping."""
    diagnostics: list[str] = []
    tradier = _credential(
        values, "ASA_TRADIER_ACCESS_TOKEN", "TRADIER_ACCESS_TOKEN", diagnostics
    )
    finnhub = _credential(values, "ASA_FINNHUB_API_KEY", "FINNHUB_API_KEY", diagnostics)
    alpha = _credential(
        values, "ASA_ALPHA_VANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEY", diagnostics
    )
    raw_tradier_environment = values.get("ASA_TRADIER_ENV", "sandbox").strip().lower()
    try:
        tradier_environment = ProviderEndpointEnvironment(raw_tradier_environment)
    except ValueError as exc:
        raise ConfigurationError(
            "Provider configuration ASA_TRADIER_ENV must be sandbox or production"
        ) from exc
    return MarketDataConfig(
        (
            _provider(
                values,
                "deterministic_fixture",
                None,
                default_enabled=True,
                endpoint_environment=ProviderEndpointEnvironment.SANDBOX,
            ),
            _provider(values, "tradier", tradier, endpoint_environment=tradier_environment),
            _provider(values, "finnhub", finnhub),
            _provider(values, "alpha_vantage", alpha),
        ),
        tuple(diagnostics),
    )


def load_market_data_config_from_environment() -> MarketDataConfig:
    """The sole Market Data environment boundary; providers never read environment state."""
    return load_market_data_config(os.environ)
