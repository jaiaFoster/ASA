"""Provider-neutral, non-statistical observation resolution (MD-013)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from domain import (
    EarningsEvent,
    ExpirationCycle,
    MarketCapability,
    MarketObservation,
    OptionChain,
    OptionContract,
    financial_contract_to_data,
    market_data_to_data,
)
from domain.values import DomainInvariantError, require_tz_aware


class ResolutionMethod(str, Enum):
    SINGLE_AVAILABLE = "single_available"
    EXACT_AGREEMENT = "exact_agreement"
    PROVIDER_PRIORITY = "provider_priority"
    UNRESOLVED = "unresolved"


class ConfidenceClassification(str, Enum):
    SINGLE_SOURCE = "single_source"
    EXACT_AGREEMENT = "exact_agreement"
    DISAGREEMENT = "disagreement"
    INSUFFICIENT_QUALITY = "insufficient_quality"


@dataclass(frozen=True, slots=True)
class ResolutionPolicy:
    policy_version: str
    provider_priority: tuple[str, ...]
    freshness_threshold_seconds: int
    required_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.policy_version or self.policy_version != self.policy_version.strip():
            raise DomainInvariantError("ResolutionPolicy policy_version must be normalized")
        if not self.provider_priority or len(set(self.provider_priority)) != len(
            self.provider_priority
        ):
            raise DomainInvariantError("ResolutionPolicy requires unique provider priority")
        if any(not item or item != item.strip() for item in self.provider_priority):
            raise DomainInvariantError("ResolutionPolicy provider IDs must be normalized")
        if (
            type(self.freshness_threshold_seconds) is not int
            or self.freshness_threshold_seconds < 0
        ):
            raise DomainInvariantError("ResolutionPolicy freshness threshold must be non-negative")
        fields = tuple(sorted(set(self.required_fields)))
        if not fields or any(not item or item != item.strip() for item in fields):
            raise DomainInvariantError("ResolutionPolicy requires normalized fields")
        object.__setattr__(self, "required_fields", fields)


@dataclass(frozen=True, slots=True)
class FieldDisagreement:
    field_path: str
    values_by_provider: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.field_path or self.field_path != self.field_path.strip():
            raise DomainInvariantError("FieldDisagreement path must be normalized")
        if len(self.values_by_provider) < 2:
            raise DomainInvariantError("FieldDisagreement requires multiple contributors")


@dataclass(frozen=True, slots=True)
class ResolutionConfidence:
    classification: ConfidenceClassification
    contributor_count: int
    fresh_contributor_count: int
    complete_contributor_count: int
    exact_agreement: bool

    def __post_init__(self) -> None:
        for name in ("contributor_count", "fresh_contributor_count", "complete_contributor_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0 or value > self.contributor_count:
                raise DomainInvariantError(f"ResolutionConfidence {name} is invalid")


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    capability: MarketCapability
    selected_observation: MarketObservation | None
    consumed_observation_ids: tuple[str, ...]
    contributors: tuple[str, ...]
    method: ResolutionMethod
    disagreements: tuple[FieldDisagreement, ...]
    confidence: ResolutionConfidence
    policy_version: str
    policy_parameters: tuple[tuple[str, str], ...]
    rationale: str

    def __post_init__(self) -> None:
        if not self.consumed_observation_ids or not self.contributors:
            raise DomainInvariantError("ResolutionResult requires consumed evidence")
        if (self.method is ResolutionMethod.UNRESOLVED) != (self.selected_observation is None):
            raise DomainInvariantError("ResolutionResult selection and method are inconsistent")
        if not self.rationale or self.rationale != self.rationale.strip():
            raise DomainInvariantError("ResolutionResult rationale must be normalized")


class ObservationResolver:
    """Selects one reported value by frozen priority or leaves the conflict unresolved."""

    def resolve(
        self,
        observations: tuple[MarketObservation, ...],
        policy: ResolutionPolicy,
        *,
        as_of: datetime,
    ) -> ResolutionResult:
        require_tz_aware(as_of, "ObservationResolver", "as_of")
        ordered = tuple(sorted(observations, key=lambda item: item.observation_id))
        if not ordered:
            raise DomainInvariantError("Observation resolution requires observations")
        capability = ordered[0].capability
        subject = ordered[0].subject
        if any(item.capability is not capability or item.subject != subject for item in ordered):
            raise DomainInvariantError("Observation resolution requires one capability and subject")
        providers = tuple(item.provenance.provider_id for item in ordered)
        if len(providers) != len(set(providers)):
            raise DomainInvariantError("Observation resolution requires one value per provider")

        by_provider = {item.provenance.provider_id: item for item in ordered}
        eligible = tuple(item for item in policy.provider_priority if item in by_provider)
        consumed_ids = tuple(item.observation_id for item in ordered)
        contributors = tuple(sorted(providers))
        values = {item.provenance.provider_id: self._value_data(item) for item in ordered}
        disagreements = self._disagreements(values)
        fresh = tuple(
            item
            for item in ordered
            if max(0, int((as_of - item.effective_time).total_seconds()))
            <= policy.freshness_threshold_seconds
        )
        complete = tuple(
            item
            for item in ordered
            if not (set(policy.required_fields) - set(item.completeness.present_fields))
        )
        exact = not disagreements
        confidence = ResolutionConfidence(
            ConfidenceClassification.EXACT_AGREEMENT
            if exact and len(ordered) > 1
            else ConfidenceClassification.SINGLE_SOURCE
            if len(ordered) == 1
            else ConfidenceClassification.DISAGREEMENT,
            len(ordered),
            len(fresh),
            len(complete),
            exact,
        )
        parameters = (
            ("freshness_threshold_seconds", str(policy.freshness_threshold_seconds)),
            ("provider_priority", ",".join(policy.provider_priority)),
            ("required_fields", ",".join(policy.required_fields)),
        )

        selected = by_provider[eligible[0]] if eligible else None
        if selected is None or selected not in fresh or selected not in complete:
            return ResolutionResult(
                capability,
                None,
                consumed_ids,
                contributors,
                ResolutionMethod.UNRESOLVED,
                disagreements,
                ResolutionConfidence(
                    ConfidenceClassification.INSUFFICIENT_QUALITY,
                    len(ordered),
                    len(fresh),
                    len(complete),
                    exact,
                ),
                policy.policy_version,
                parameters,
                "highest-priority available observation did not satisfy explicit quality inputs",
            )
        method = (
            ResolutionMethod.SINGLE_AVAILABLE
            if len(ordered) == 1
            else ResolutionMethod.EXACT_AGREEMENT
            if exact
            else ResolutionMethod.PROVIDER_PRIORITY
        )
        return ResolutionResult(
            capability,
            selected,
            consumed_ids,
            contributors,
            method,
            disagreements,
            confidence,
            policy.policy_version,
            parameters,
            "selected one complete reported value using frozen provider priority",
        )

    @staticmethod
    def _value_data(observation: MarketObservation) -> dict[str, object]:
        if isinstance(
            observation.value, (OptionContract, OptionChain, ExpirationCycle, EarningsEvent)
        ):
            data = financial_contract_to_data(observation.value)
        else:
            data = market_data_to_data(observation.value)
        if not isinstance(data, dict):
            raise DomainInvariantError("Market observation value must serialize as an object")
        return data

    @classmethod
    def _disagreements(cls, values: dict[str, dict[str, object]]) -> tuple[FieldDisagreement, ...]:
        flattened = {provider: cls._flatten(value) for provider, value in values.items()}
        paths = sorted({path for value in flattened.values() for path in value})
        output: list[FieldDisagreement] = []
        for path in paths:
            contributors = tuple(
                sorted(
                    (provider, value.get(path, "<missing>"))
                    for provider, value in flattened.items()
                )
            )
            if len({value for _, value in contributors}) > 1:
                output.append(FieldDisagreement(path, contributors))
        return tuple(output)

    @staticmethod
    def _flatten(value: object, prefix: str = "") -> dict[str, str]:
        if isinstance(value, dict):
            output: dict[str, str] = {}
            for key in sorted(value):
                child = f"{prefix}.{key}" if prefix else str(key)
                output.update(ObservationResolver._flatten(value[key], child))
            return output
        if isinstance(value, list):
            output = {}
            for index, item in enumerate(value):
                child = f"{prefix}[{index}]"
                output.update(ObservationResolver._flatten(item, child))
            return output
        return {prefix: json.dumps(value, sort_keys=True, separators=(",", ":"))}
