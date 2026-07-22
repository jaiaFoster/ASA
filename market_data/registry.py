"""Closed Provider inventory and capability-driven discovery (MD-005)."""

from __future__ import annotations

from dataclasses import dataclass

from domain import MarketCapability
from domain.values import DomainInvariantError
from market_data.providers import (
    HealthProbe,
    MarketDataProvider,
    ProviderHealthReport,
    ProviderMetadata,
    ProviderShutdownReport,
    ProviderStatus,
    ProviderValidationPlan,
    ProviderValidationReport,
)


def _text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise DomainInvariantError(f"{owner}.{field_name} must be normalized text")


class ProviderRegistry:
    """Immutable inventory closed before acquisition begins."""

    __slots__ = ("_providers",)

    def __init__(self, providers: tuple[MarketDataProvider, ...]) -> None:
        ordered = tuple(sorted(providers, key=lambda value: value.provider_id))
        ids = tuple(value.provider_id for value in ordered)
        if not ordered:
            raise DomainInvariantError("ProviderRegistry requires providers")
        if len(ids) != len(set(ids)):
            raise DomainInvariantError("ProviderRegistry provider IDs must be unique")
        if any(value.provider_id != value.metadata.identity.provider_id for value in ordered):
            raise DomainInvariantError("ProviderRegistry metadata identity mismatch")
        self._providers = ordered

    @property
    def providers(self) -> tuple[MarketDataProvider, ...]:
        return self._providers

    def provider(self, provider_id: str) -> MarketDataProvider:
        matches = tuple(value for value in self._providers if value.provider_id == provider_id)
        if len(matches) != 1:
            raise DomainInvariantError(f"Unknown Provider {provider_id!r}")
        return matches[0]

    def metadata(self) -> tuple[ProviderMetadata, ...]:
        return tuple(value.metadata for value in self._providers)

    def providers_for(self, capability: MarketCapability) -> tuple[MarketDataProvider, ...]:
        return tuple(value for value in self._providers if capability in value.capabilities)

    def health(self, probe: HealthProbe) -> tuple[ProviderHealthReport, ...]:
        return tuple(value.health(probe) for value in self._providers)

    def validate(
        self, plans: tuple[ProviderValidationPlan, ...]
    ) -> tuple[ProviderValidationReport, ...]:
        ordered = tuple(sorted(plans, key=lambda value: value.provider_id))
        if len({value.provider_id for value in ordered}) != len(ordered):
            raise DomainInvariantError("Provider validation plans must be unique by provider")
        return tuple(self.provider(plan.provider_id).validate(plan) for plan in ordered)

    def shutdown(self) -> tuple[ProviderShutdownReport, ...]:
        return tuple(value.shutdown() for value in self._providers)


@dataclass(frozen=True, slots=True)
class ProviderPriority:
    capability: MarketCapability
    provider_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.provider_ids:
            raise DomainInvariantError("ProviderPriority requires provider IDs")
        if any(not value or value != value.strip() for value in self.provider_ids):
            raise DomainInvariantError("ProviderPriority IDs must be normalized")
        if len(self.provider_ids) != len(set(self.provider_ids)):
            raise DomainInvariantError("ProviderPriority IDs must be unique")


@dataclass(frozen=True, slots=True)
class ProviderPriorityPolicy:
    policy_version: str
    priorities: tuple[ProviderPriority, ...]

    def __post_init__(self) -> None:
        _text(self.policy_version, "ProviderPriorityPolicy", "policy_version")
        priorities = tuple(sorted(self.priorities, key=lambda value: value.capability.value))
        capabilities = tuple(value.capability for value in priorities)
        if not priorities or len(capabilities) != len(set(capabilities)):
            raise DomainInvariantError("ProviderPriorityPolicy capabilities must be unique")
        object.__setattr__(self, "priorities", priorities)

    def for_capability(self, capability: MarketCapability) -> ProviderPriority:
        matches = tuple(value for value in self.priorities if value.capability is capability)
        if len(matches) != 1:
            raise DomainInvariantError(f"No priority policy for {capability.value}")
        return matches[0]


@dataclass(frozen=True, slots=True)
class ProviderCandidate:
    provider_id: str
    capability: MarketCapability
    priority: int
    status: ProviderStatus
    status_detail_code: str

    def __post_init__(self) -> None:
        _text(self.provider_id, "ProviderCandidate", "provider_id")
        _text(self.status_detail_code, "ProviderCandidate", "status_detail_code")
        if type(self.priority) is not int or self.priority < 1:
            raise DomainInvariantError("ProviderCandidate.priority must be positive")


class CapabilityRegistry:
    """Deterministic lookup from canonical capability to visible candidates."""

    __slots__ = ("_providers", "_policy")

    def __init__(
        self, provider_registry: ProviderRegistry, priority_policy: ProviderPriorityPolicy
    ) -> None:
        registered = {value.provider_id for value in provider_registry.providers}
        for priority in priority_policy.priorities:
            unknown = set(priority.provider_ids) - registered
            if unknown:
                raise DomainInvariantError("Capability priority references unknown Provider")
            declared = {
                value.provider_id
                for value in provider_registry.providers_for(priority.capability)
            }
            if not set(priority.provider_ids).issubset(declared):
                raise DomainInvariantError("Capability priority contradicts Provider declarations")
        self._providers = provider_registry
        self._policy = priority_policy

    @property
    def policy(self) -> ProviderPriorityPolicy:
        return self._policy

    def lookup(
        self,
        capability: MarketCapability,
        health_reports: tuple[ProviderHealthReport, ...] = (),
    ) -> tuple[ProviderCandidate, ...]:
        statuses = {value.provider_id: value for value in health_reports}
        if len(statuses) != len(health_reports):
            raise DomainInvariantError("Health reports must be unique by provider")
        priority = self._policy.for_capability(capability)
        return tuple(
            ProviderCandidate(
                provider_id,
                capability,
                index,
                statuses[provider_id].status
                if provider_id in statuses
                else ProviderStatus.UNKNOWN,
                statuses[provider_id].detail_code if provider_id in statuses else "NOT_CHECKED",
            )
            for index, provider_id in enumerate(priority.provider_ids, start=1)
        )
