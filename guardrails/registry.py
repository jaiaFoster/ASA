"""Guardrail registry (ASA-CORE-006).

Registers deterministic guardrail check implementations by
``guardrail_id`` string, so the engine dispatches via lookup rather than
embedding an ``if guardrail_id == ...`` chain. Explicit registration,
deterministic lookup, duplicate registration rejected. Mirrors
``indicators/registry.py`` and ``strategies/registry.py`` exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domain.opportunity import Opportunity
from guardrails.errors import DuplicateGuardrailRegistrationError, UnknownGuardrailIdError
from guardrails.evaluations import (
    allowed_time_horizon,
    maximum_capital_required,
    maximum_loss,
    minimum_evidence_confidence,
    placeholder_metrics_rejection,
)

GuardrailCheckFn = Callable[[Opportunity, dict], "tuple[bool, str]"]


@dataclass(frozen=True)
class GuardrailDefinition:
    """A registered guardrail's check function and its pinned policy version.

    ``guardrail_version`` is what ``GuardrailOutcome.guardrail_version``
    pins (ADR-005) — bump it whenever ``check``'s policy semantics change.
    """

    guardrail_id: str
    guardrail_version: str
    check: GuardrailCheckFn


class GuardrailRegistry:
    """Explicit guardrail_id -> GuardrailDefinition registry."""

    def __init__(self) -> None:
        self._definitions: dict[str, GuardrailDefinition] = {}

    def register(self, guardrail_id: str, guardrail_version: str,
                 check: GuardrailCheckFn) -> None:
        if guardrail_id in self._definitions:
            raise DuplicateGuardrailRegistrationError(guardrail_id)
        self._definitions[guardrail_id] = GuardrailDefinition(
            guardrail_id=guardrail_id, guardrail_version=guardrail_version, check=check,
        )

    def get(self, guardrail_id: str) -> GuardrailDefinition:
        try:
            return self._definitions[guardrail_id]
        except KeyError:
            raise UnknownGuardrailIdError(guardrail_id) from None

    def is_registered(self, guardrail_id: str) -> bool:
        return guardrail_id in self._definitions

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions.keys()))


def build_default_registry() -> GuardrailRegistry:
    """Registry pre-loaded with the five required guardrails (ASA-CORE-006)."""
    registry = GuardrailRegistry()
    registry.register("minimum_evidence_confidence", "v1", minimum_evidence_confidence)
    registry.register("maximum_capital_required", "v1", maximum_capital_required)
    registry.register("maximum_loss", "v1", maximum_loss)
    registry.register("allowed_time_horizon", "v1", allowed_time_horizon)
    registry.register("placeholder_metrics_rejection", "v1", placeholder_metrics_rejection)
    return registry


DEFAULT_REGISTRY = build_default_registry()
