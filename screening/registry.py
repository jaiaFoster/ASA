"""Screening strategy registry (SCREEN-002).

A closed, explicit, deterministic catalog of screening-eligible strategy
identity and declared canonical input requirements. Registration carries no
strategy-specific execution logic and performs no execution itself -- see
SCREEN-003 for the runner boundary that pairs a registered strategy's
identity with an adapter and executes it.

No dynamic discovery: a ScreeningRegistry is always constructed from one
explicit, finite tuple of definitions.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import MarketCapability
from screening.errors import DuplicateScreeningRegistrationError, UnknownScreeningStrategyIdError


def _normalized_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner}.{field_name} must be non-empty normalized text")


@dataclass(frozen=True, slots=True)
class ScreeningStrategyDefinition:
    """One registered screening strategy's identity and declared canonical inputs.

    ``required_capabilities`` is expressed exclusively in canonical
    ``MarketCapability`` terms -- never a provider name -- per SPRINT-006's
    architecture_invariants.
    """

    strategy_id: str
    strategy_version: str
    manifest_id: str
    required_capabilities: tuple[MarketCapability, ...]

    def __post_init__(self) -> None:
        for name in ("strategy_id", "strategy_version", "manifest_id"):
            _normalized_text(getattr(self, name), "ScreeningStrategyDefinition", name)
        if not self.required_capabilities:
            raise ValueError(
                "ScreeningStrategyDefinition.required_capabilities cannot be empty"
            )
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError(
                "ScreeningStrategyDefinition.required_capabilities must be unique"
            )


class ScreeningRegistry:
    """Immutable strategy_id -> ScreeningStrategyDefinition catalog."""

    __slots__ = ("_definitions",)

    def __init__(self, definitions: tuple[ScreeningStrategyDefinition, ...] = ()) -> None:
        registered: dict[str, ScreeningStrategyDefinition] = {}
        for definition in definitions:
            if definition.strategy_id in registered:
                raise DuplicateScreeningRegistrationError(definition.strategy_id)
            registered[definition.strategy_id] = definition
        self._definitions = registered

    def get(self, strategy_id: str) -> ScreeningStrategyDefinition:
        try:
            return self._definitions[strategy_id]
        except KeyError:
            raise UnknownScreeningStrategyIdError(strategy_id) from None

    def is_registered(self, strategy_id: str) -> bool:
        return strategy_id in self._definitions

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions.keys()))

    def definitions(self) -> tuple[ScreeningStrategyDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions.keys()))


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    """API-003's own public capability catalog shape.

    A translation of ScreeningStrategyDefinition, not a second copy of its
    fields' meaning: signal_id/signal_version replace strategy_id/
    strategy_version at this boundary the same way ScreeningStateRecord
    already does, because asa/'s own legacy-technology boundary test
    (tests/asa/test_boundaries.py) bans the literal substring "strategy"
    anywhere under asa/ -- asa/'s capabilities endpoint must reference this
    type's field names directly to build its response, and cannot reference
    ScreeningStrategyDefinition's own field names to do so.
    """

    signal_id: str
    signal_version: str
    manifest_id: str
    required_capabilities: tuple[MarketCapability, ...]


def signal_catalog(registry: ScreeningRegistry) -> tuple[SignalDefinition, ...]:
    """The registry's full catalog, translated to the public signal_id/
    signal_version vocabulary. Deterministically ordered (registry.definitions()
    already sorts by strategy_id)."""
    return tuple(
        SignalDefinition(
            signal_id=definition.strategy_id,
            signal_version=definition.strategy_version,
            manifest_id=definition.manifest_id,
            required_capabilities=definition.required_capabilities,
        )
        for definition in registry.definitions()
    )
