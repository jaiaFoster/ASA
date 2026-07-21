"""Guardrail engine and registry errors (ASA-CORE-006)."""
from __future__ import annotations


class GuardrailError(Exception):
    """Base error for all guardrail operations."""


# ---------------------------------------------------------------------------
# Evaluation errors
# ---------------------------------------------------------------------------

class InvalidGuardrailParameterError(GuardrailError):
    """A required guardrail parameter is missing or has an invalid value/type."""

    def __init__(self, guardrail_id: str, message: str) -> None:
        super().__init__(f"{guardrail_id}: {message}")
        self.guardrail_id = guardrail_id


class EmptyOpportunityEvidenceError(GuardrailError):
    """An Opportunity has no evidence and no supporting indicators — a
    Guardrail outcome would have nothing to cite. Strategies always
    populate at least one (ADR-003); this indicates a malformed
    Opportunity, not a legitimate empty case."""

    def __init__(self, opportunity_id: str) -> None:
        super().__init__(
            f"opportunity {opportunity_id} has no evidence or supporting "
            f"indicators to cite"
        )
        self.opportunity_id = opportunity_id


# ---------------------------------------------------------------------------
# Registry errors
# ---------------------------------------------------------------------------

class DuplicateGuardrailRegistrationError(GuardrailError):
    """A guardrail_id was registered more than once."""

    def __init__(self, guardrail_id: str) -> None:
        super().__init__(f"guardrail_id already registered: {guardrail_id!r}")
        self.guardrail_id = guardrail_id


class UnknownGuardrailIdError(GuardrailError):
    """No check is registered for the requested guardrail_id."""

    def __init__(self, guardrail_id: str) -> None:
        super().__init__(f"no guardrail registered for id: {guardrail_id!r}")
        self.guardrail_id = guardrail_id
