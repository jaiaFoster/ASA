"""Execution Planner errors."""


class ExecutionPlanningError(ValueError):
    """Base error for deterministic execution planning."""


class InvalidPlanningParameterError(ExecutionPlanningError):
    """Raised when v1 planning policy is not supported."""


class UnplannableDecisionError(ExecutionPlanningError):
    """Raised when approved exposure cannot produce a non-zero deterministic delta."""
