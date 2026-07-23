"""Errors for strategy_runtime (SPRINT-009)."""

from __future__ import annotations


class StrategyContractError(ValueError):
    """Raised when a StrategyContract or one of its nested declarations is invalid."""


class UnknownStrategyIdError(KeyError):
    """Raised when a strategy_id is not registered in a StrategyRegistry."""


class DuplicateStrategyRegistrationError(ValueError):
    """Raised when two contracts register the same strategy_id in one StrategyRegistry."""
