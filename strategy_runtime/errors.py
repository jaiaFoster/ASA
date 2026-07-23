"""Errors for strategy_runtime (SPRINT-009)."""

from __future__ import annotations


class StrategyContractError(ValueError):
    """Raised when a StrategyContract or one of its nested declarations is invalid."""
