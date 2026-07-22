"""Derived analytics feature registry (ANALYTICS-001).

A closed, explicit, deterministic catalog of derived-feature identity and
declared canonical input requirements -- mirrors screening/registry.py's
design exactly. No dynamic discovery: an AnalyticsRegistry is always
constructed from one explicit, finite tuple of definitions.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import MarketCapability
from analytics.errors import DuplicateFeatureRegistrationError, UnknownFeatureIdError


def _normalized_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner}.{field_name} must be non-empty normalized text")


@dataclass(frozen=True, slots=True)
class AnalyticsFeatureDefinition:
    """One registered derived feature's identity and declared canonical inputs.

    ``required_capabilities`` is expressed exclusively in canonical
    ``MarketCapability`` terms -- never a provider name -- matching the
    canonical capability model this sprint's architecture_invariants require.
    """

    feature_id: str
    feature_version: str
    description: str
    required_capabilities: tuple[MarketCapability, ...]

    def __post_init__(self) -> None:
        for name in ("feature_id", "feature_version", "description"):
            _normalized_text(getattr(self, name), "AnalyticsFeatureDefinition", name)
        if not self.required_capabilities:
            raise ValueError(
                "AnalyticsFeatureDefinition.required_capabilities cannot be empty"
            )
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError(
                "AnalyticsFeatureDefinition.required_capabilities must be unique"
            )


class AnalyticsRegistry:
    """Immutable feature_id -> AnalyticsFeatureDefinition catalog."""

    __slots__ = ("_definitions",)

    def __init__(self, definitions: tuple[AnalyticsFeatureDefinition, ...] = ()) -> None:
        registered: dict[str, AnalyticsFeatureDefinition] = {}
        for definition in definitions:
            if definition.feature_id in registered:
                raise DuplicateFeatureRegistrationError(definition.feature_id)
            registered[definition.feature_id] = definition
        self._definitions = registered

    def get(self, feature_id: str) -> AnalyticsFeatureDefinition:
        try:
            return self._definitions[feature_id]
        except KeyError:
            raise UnknownFeatureIdError(feature_id) from None

    def is_registered(self, feature_id: str) -> bool:
        return feature_id in self._definitions

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions.keys()))

    def definitions(self) -> tuple[AnalyticsFeatureDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions.keys()))
