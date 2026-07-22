"""Reusable offline Provider compliance evaluation (MD-016)."""

from __future__ import annotations

from dataclasses import dataclass

from domain import MarketCapability
from domain.values import DomainInvariantError
from market_data.providers import MarketDataProvider, ProviderFetchResult


@dataclass(frozen=True, slots=True)
class ProviderCapabilityCase:
    capability: MarketCapability
    result: ProviderFetchResult


@dataclass(frozen=True, slots=True)
class ProviderComplianceReport:
    provider_id: str
    adapter_version: str
    covered_capabilities: tuple[MarketCapability, ...]
    passed: bool

    def __post_init__(self) -> None:
        if not self.provider_id or not self.adapter_version:
            raise DomainInvariantError("ProviderComplianceReport identity must be non-empty")
        if not self.covered_capabilities or not self.passed:
            raise DomainInvariantError("ProviderComplianceReport represents passing coverage only")


def evaluate_provider_compliance(
    provider: MarketDataProvider,
    cases: tuple[ProviderCapabilityCase, ...],
) -> ProviderComplianceReport:
    """Fail closed unless every declared capability has one canonical successful fixture."""

    by_capability = {case.capability: case for case in cases}
    if len(by_capability) != len(cases):
        raise DomainInvariantError("Provider compliance cases must be unique by capability")
    declared = set(provider.capabilities)
    if set(by_capability) != declared:
        raise DomainInvariantError("Provider compliance must cover every declared capability")
    if set(provider.metadata.fixture_coverage) != declared:
        raise DomainInvariantError("Provider fixture coverage must match declared capabilities")
    for capability in sorted(declared, key=lambda item: item.value):
        result = by_capability[capability].result
        if result.error is not None or not result.observations or not result.attempts:
            raise DomainInvariantError("Provider compliance requires a successful canonical result")
        if any(item.capability is not capability for item in result.observations):
            raise DomainInvariantError("Provider compliance result capability mismatch")
        if any(item.provenance.provider_id != provider.provider_id for item in result.observations):
            raise DomainInvariantError("Provider compliance provenance mismatch")
        if any(item.completeness.missing_fields for item in result.observations):
            raise DomainInvariantError("Provider compliance fixture is incomplete")
        if any(item.provider_id != provider.provider_id for item in result.attempts):
            raise DomainInvariantError("Provider compliance attempt identity mismatch")
    return ProviderComplianceReport(
        provider.provider_id,
        provider.metadata.identity.adapter_version,
        tuple(sorted(declared, key=lambda item: item.value)),
        True,
    )
