"""Reconciliation errors (ASA-CORE-003)."""
from __future__ import annotations


class ReconciliationError(Exception):
    """Base error for reconciliation operations."""


class InconsistentGroupError(ReconciliationError):
    """Observations passed to reconcile() do not share fact_type/effective_time.

    The reconciliation engine reconciles exactly one (fact_type,
    effective_time) group at a time (ASA-CORE-003 v1 grouping — see
    ``reconciliation/rules.py`` module docstring); mixed-group input is a
    caller error, not something the engine silently repairs.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class EmptyObservationGroupError(ReconciliationError):
    """reconcile() was called with zero observations."""

    def __init__(self) -> None:
        super().__init__("reconcile() requires at least one observation")
