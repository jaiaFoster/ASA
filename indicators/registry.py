"""Indicator registry (ASA-CORE-004).

Registers deterministic indicator calculation implementations by
``indicator_type`` string, so the engine dispatches via lookup rather than
embedding an ``if indicator_type == ...`` chain. Explicit registration,
deterministic lookup, duplicate registration rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domain.canonical_fact import CanonicalFact
from indicators.calculations import (
    exponential_moving_average,
    latest_price,
    price_change_percent,
    rolling_high,
    rolling_low,
    simple_moving_average,
)
from indicators.errors import DuplicateIndicatorRegistrationError, UnknownIndicatorTypeError

IndicatorComputeFn = Callable[
    [tuple[CanonicalFact, ...], dict], tuple[object, tuple[CanonicalFact, ...]]
]


@dataclass(frozen=True)
class IndicatorDefinition:
    """A registered indicator's compute function and its calculation-logic version.

    ``logic_version`` is what an Indicator's ``computed_from``/``logic_version``
    field pins (ADR-006) — bump it whenever ``compute`` changes semantics.
    """

    indicator_type: str
    logic_version: str
    compute: IndicatorComputeFn


class IndicatorRegistry:
    """Explicit indicator_type -> IndicatorDefinition registry."""

    def __init__(self) -> None:
        self._definitions: dict[str, IndicatorDefinition] = {}

    def register(self, indicator_type: str, logic_version: str,
                 compute: IndicatorComputeFn) -> None:
        if indicator_type in self._definitions:
            raise DuplicateIndicatorRegistrationError(indicator_type)
        self._definitions[indicator_type] = IndicatorDefinition(
            indicator_type=indicator_type, logic_version=logic_version, compute=compute,
        )

    def get(self, indicator_type: str) -> IndicatorDefinition:
        try:
            return self._definitions[indicator_type]
        except KeyError:
            raise UnknownIndicatorTypeError(indicator_type) from None

    def is_registered(self, indicator_type: str) -> bool:
        return indicator_type in self._definitions

    def registered_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions.keys()))


def build_default_registry() -> IndicatorRegistry:
    """Registry pre-loaded with the six required indicators (ASA-CORE-004)."""
    registry = IndicatorRegistry()
    registry.register("latest_price", "v1", latest_price)
    registry.register("price_change_percent", "v1", price_change_percent)
    registry.register("simple_moving_average", "v1", simple_moving_average)
    registry.register("exponential_moving_average", "v1", exponential_moving_average)
    registry.register("rolling_high", "v1", rolling_high)
    registry.register("rolling_low", "v1", rolling_low)
    return registry


DEFAULT_REGISTRY = build_default_registry()
