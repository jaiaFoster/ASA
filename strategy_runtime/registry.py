"""Strategy registration and discovery (SPRINT-009/EPIC-1).

StrategyRegistry is the universal-runtime equivalent of
screening.registry.ScreeningRegistry -- an immutable strategy_id ->
(StrategyContract, adapter) catalog -- generalized to hold any adapter
return type (TResult), not only ScreeningResult, and driven by the new
StrategyContract (EPIC-2) rather than ScreeningStrategyDefinition. No
dynamic discovery: a StrategyRegistry is always constructed from one
explicit, finite set of registrations, matching ScreeningRegistry's own
established convention exactly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from strategy_runtime.context import RuntimeContext
from strategy_runtime.contract import StrategyContract
from strategy_runtime.errors import DuplicateStrategyRegistrationError, UnknownStrategyIdError

# Python 3.11-compatible TypeVar/Generic, not PEP 695 syntax: this
# package's tests are collected by validate-architecture.yml under
# Python 3.11 (that workflow's own setup-python step, unrelated to this
# project's own >=3.12 requirement), which does not support "class
# Foo[T]:". Confirmed the hard way -- an earlier version of this file
# used PEP 695 syntax and broke that workflow with a SyntaxError.
TResult = TypeVar("TResult")

StrategyAdapter = Callable[[RuntimeContext], TResult]
"""A strategy's own evaluation logic and nothing else (this sprint's own
strategies_own_thesis principle) -- takes the context the runtime built
for one (strategy, subject) pair and returns that strategy's own result.
Orchestration, retries, and error isolation are the runtime's job
(strategy_runtime.execution), never the adapter's own.
"""


class StrategyRegistry(Generic[TResult]):
    __slots__ = ("_entries",)

    def __init__(
        self, entries: tuple[tuple[StrategyContract, StrategyAdapter[TResult]], ...] = ()
    ) -> None:
        registered: dict[str, tuple[StrategyContract, StrategyAdapter[TResult]]] = {}
        for contract, adapter in entries:
            if contract.strategy_id in registered:
                raise DuplicateStrategyRegistrationError(contract.strategy_id)
            registered[contract.strategy_id] = (contract, adapter)
        self._entries = registered

    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def is_registered(self, strategy_id: str) -> bool:
        return strategy_id in self._entries

    def contract_for(self, strategy_id: str) -> StrategyContract:
        try:
            return self._entries[strategy_id][0]
        except KeyError:
            raise UnknownStrategyIdError(strategy_id) from None

    def adapter_for(self, strategy_id: str) -> StrategyAdapter[TResult]:
        try:
            return self._entries[strategy_id][1]
        except KeyError:
            raise UnknownStrategyIdError(strategy_id) from None

    def contracts(self) -> tuple[StrategyContract, ...]:
        return tuple(self._entries[key][0] for key in sorted(self._entries))
