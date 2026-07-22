"""Screening framework errors (SCREEN-002)."""

from __future__ import annotations


class ScreeningError(Exception):
    """Base error for all screening framework operations."""


class DuplicateScreeningRegistrationError(ScreeningError):
    """A strategy_id was registered more than once in a ScreeningRegistry."""

    def __init__(self, strategy_id: str) -> None:
        super().__init__(f"strategy_id already registered: {strategy_id!r}")
        self.strategy_id = strategy_id


class UnknownScreeningStrategyIdError(ScreeningError):
    """No screening strategy is registered for the requested strategy_id."""

    def __init__(self, strategy_id: str) -> None:
        super().__init__(f"no screening strategy registered for id: {strategy_id!r}")
        self.strategy_id = strategy_id
