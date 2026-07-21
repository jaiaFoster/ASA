"""Strategy registry (ASA-CORE-005).

Registers deterministic strategy calculation implementations by
``strategy_id`` string, so the engine dispatches via lookup rather than
embedding an ``if strategy_id == ...`` chain. Explicit registration,
deterministic lookup, duplicate registration rejected. Mirrors
``indicators/registry.py``'s design exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domain.canonical_fact import CanonicalFact
from domain.indicator import Indicator
from strategies.calculations import breakout, momentum, moving_average_crossover
from strategies.errors import DuplicateStrategyRegistrationError, UnknownStrategyIdError
from strategies.signal import StrategySignal

StrategyComputeFn = Callable[
    [dict[str, Indicator], tuple[CanonicalFact, ...], dict], "StrategySignal | None"
]


@dataclass(frozen=True)
class StrategyDefinition:
    """A registered strategy's compute function and its pinned strategy version.

    ``strategy_version`` is what ``Opportunity.strategy_version`` pins
    (ADR-003) — bump it whenever ``compute``'s semantics change.
    """

    strategy_id: str
    strategy_version: str
    compute: StrategyComputeFn


class StrategyRegistry:
    """Explicit strategy_id -> StrategyDefinition registry."""

    def __init__(self) -> None:
        self._definitions: dict[str, StrategyDefinition] = {}

    def register(self, strategy_id: str, strategy_version: str, compute: StrategyComputeFn) -> None:
        if strategy_id in self._definitions:
            raise DuplicateStrategyRegistrationError(strategy_id)
        self._definitions[strategy_id] = StrategyDefinition(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            compute=compute,
        )

    def get(self, strategy_id: str) -> StrategyDefinition:
        try:
            return self._definitions[strategy_id]
        except KeyError:
            raise UnknownStrategyIdError(strategy_id) from None

    def is_registered(self, strategy_id: str) -> bool:
        return strategy_id in self._definitions

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions.keys()))


def build_default_registry() -> StrategyRegistry:
    """Registry pre-loaded with the three required strategies (ASA-CORE-005)."""
    registry = StrategyRegistry()
    registry.register("moving_average_crossover", "v1", moving_average_crossover)
    registry.register("breakout", "v1", breakout)
    registry.register("momentum", "v1", momentum)
    return registry


DEFAULT_REGISTRY = build_default_registry()
