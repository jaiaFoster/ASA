"""Errors for strategy_runtime (SPRINT-009)."""

from __future__ import annotations


class StrategyContractError(ValueError):
    """Raised when a StrategyContract or one of its nested declarations is invalid."""


class UnknownStrategyIdError(KeyError):
    """Raised when a strategy_id is not registered in a StrategyRegistry."""


class DuplicateStrategyRegistrationError(ValueError):
    """Raised when two contracts register the same strategy_id in one StrategyRegistry."""


class StrategyContractViolationError(RuntimeError):
    """Raised when a strategy's actual execution contradicts its own declared
    StrategyContract (SPRINT-009R/EPIC-R1 runtime_validation): a required
    capability was not fulfillable before execution, or a declared output was
    not emitted by the produced result. Distinct from an adapter's own
    exceptions -- this is the runtime detecting a strategy that does not do
    what its contract says it does.
    """
