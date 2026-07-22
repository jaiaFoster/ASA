"""Deterministic dependency-injected Provider construction (MD-004)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol, runtime_checkable

from domain import MarketCapability
from market_data.config import ConfigurationError, MarketDataConfig, ProviderConfig
from market_data.providers import MarketDataProvider, RequestBudgetAuthorization


class ProviderFactoryError(ConfigurationError):
    """Provider construction failed before any network operation."""


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class BudgetAuthorizer(Protocol):
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization: ...


@dataclass(frozen=True, slots=True)
class ProviderDependencies:
    transport: object
    clock: Clock
    budget_authorizer: BudgetAuthorizer


ProviderConstructor = Callable[[ProviderConfig, ProviderDependencies], MarketDataProvider]


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    adapter_type: str
    adapter_version: str
    constructor: ProviderConstructor

    def __post_init__(self) -> None:
        for name in ("adapter_type", "adapter_version"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise ProviderFactoryError(f"Provider registration {name} must be normalized")
        if not callable(self.constructor):
            raise ProviderFactoryError("Provider registration constructor must be callable")


class ProviderFactory:
    """Closed construction registry assembled once by the composition root."""

    __slots__ = ("_registrations",)

    def __init__(self, registrations: tuple[ProviderRegistration, ...]) -> None:
        ordered = tuple(
            sorted(registrations, key=lambda value: (value.adapter_type, value.adapter_version))
        )
        keys = tuple((value.adapter_type, value.adapter_version) for value in ordered)
        if not ordered:
            raise ProviderFactoryError("ProviderFactory requires static registrations")
        if len(keys) != len(set(keys)):
            raise ProviderFactoryError("Duplicate ProviderFactory registration")
        self._registrations = ordered

    @property
    def registrations(self) -> tuple[ProviderRegistration, ...]:
        return self._registrations

    def create(
        self,
        config: ProviderConfig,
        dependencies: ProviderDependencies,
    ) -> MarketDataProvider:
        if not config.enabled:
            raise ProviderFactoryError(f"Provider {config.provider_id!r} is disabled")
        if config.provider_id != "deterministic_fixture" and config.credential is None:
            raise ProviderFactoryError(
                f"Provider {config.provider_id!r} requires configured credentials"
            )
        matches = tuple(
            value
            for value in self._registrations
            if (value.adapter_type, value.adapter_version)
            == (config.adapter_type, config.adapter_version)
        )
        if len(matches) != 1:
            raise ProviderFactoryError(
                f"No unique constructor for adapter {config.adapter_type!r} version "
                f"{config.adapter_version!r}"
            )
        provider = matches[0].constructor(config, dependencies)
        if not isinstance(provider, MarketDataProvider):
            raise ProviderFactoryError("Provider constructor did not satisfy MarketDataProvider")
        if provider.provider_id != config.provider_id:
            raise ProviderFactoryError("Constructed Provider identity does not match configuration")
        return provider

    def create_enabled(
        self,
        config: MarketDataConfig,
        dependencies: ProviderDependencies,
    ) -> tuple[MarketDataProvider, ...]:
        return tuple(
            self.create(provider_config, dependencies)
            for provider_config in config.providers
            if provider_config.enabled
        )
