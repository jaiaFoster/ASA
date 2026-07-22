"""Bounded, isolated screening run orchestration (SCREEN-003).

Executes each requested registered strategy independently against its own
adapter. One strategy's exception is isolated as a STRATEGY_EXCEPTION result
and never aborts the run for any other strategy. Deterministic for
identical registry contents, adapters, requested strategy_ids, and clock
reading: run_id is derived only from those inputs, never randomness.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime

from screening.clock import Clock
from screening.errors import UnknownScreeningStrategyIdError
from screening.registry import ScreeningRegistry, ScreeningStrategyDefinition
from screening.results import ScreeningOutcomeStatus, ScreeningResult, bounded_failure_detail


class StrategyAdapterError(Exception):
    """An adapter raises this to report a clean MISSING_DATA or
    MALFORMED_OUTPUT outcome. Any other exception the adapter raises is
    isolated by the runner as STRATEGY_EXCEPTION instead.
    """

    _ALLOWED = (ScreeningOutcomeStatus.MISSING_DATA, ScreeningOutcomeStatus.MALFORMED_OUTPUT)

    def __init__(self, outcome_status: ScreeningOutcomeStatus, detail: str) -> None:
        if outcome_status not in self._ALLOWED:
            raise ValueError(
                f"StrategyAdapterError only carries {[s.value for s in self._ALLOWED]}"
            )
        super().__init__(detail)
        self.outcome_status = outcome_status
        self.detail = detail


# An adapter receives the registered definition, an injected clock, and the
# run_id already computed by the runner, and returns a fully-formed
# ScreeningResult for exactly one subject. Adapters close over whatever
# canonical input (option chain, earnings event, ...) they need internally
# (SCREEN-004); the runner knows nothing about strategy-specific inputs.
StrategyAdapter = Callable[[ScreeningStrategyDefinition, Clock, str], ScreeningResult]


def _compute_run_id(strategy_ids: tuple[str, ...], as_of: datetime) -> str:
    payload = {"strategy_ids": list(strategy_ids), "as_of": as_of.isoformat()}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _exception_result(
    run_id: str, definition: ScreeningStrategyDefinition, as_of: datetime, detail: str
) -> ScreeningResult:
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        "unknown",
        as_of,
        ScreeningOutcomeStatus.STRATEGY_EXCEPTION,
        None,
        None,
        (),
        (),
        None,
        bounded_failure_detail(detail),
    )


def _adapter_error_result(
    run_id: str,
    definition: ScreeningStrategyDefinition,
    as_of: datetime,
    error: StrategyAdapterError,
) -> ScreeningResult:
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        "unknown",
        as_of,
        error.outcome_status,
        None,
        None,
        (),
        (),
        None,
        bounded_failure_detail(error.detail),
    )


def _malformed_result(
    run_id: str, definition: ScreeningStrategyDefinition, as_of: datetime, detail: str
) -> ScreeningResult:
    return ScreeningResult(
        run_id,
        definition.strategy_id,
        definition.strategy_version,
        "unknown",
        as_of,
        ScreeningOutcomeStatus.MALFORMED_OUTPUT,
        None,
        None,
        (),
        (),
        None,
        bounded_failure_detail(detail),
    )


def _run_one(
    run_id: str,
    definition: ScreeningStrategyDefinition,
    adapter: StrategyAdapter,
    clock: Clock,
    as_of: datetime,
) -> ScreeningResult:
    try:
        result = adapter(definition, clock, run_id)
    except StrategyAdapterError as error:
        return _adapter_error_result(run_id, definition, as_of, error)
    except Exception as exc:  # noqa: BLE001 -- deliberate per-strategy isolation boundary
        return _exception_result(
            run_id, definition, as_of, f"{type(exc).__name__}: unhandled adapter exception"
        )
    if not isinstance(result, ScreeningResult):
        return _malformed_result(run_id, definition, as_of, "adapter did not return a ScreeningResult")
    if (
        result.strategy_id != definition.strategy_id
        or result.strategy_version != definition.strategy_version
        or result.run_id != run_id
    ):
        return _malformed_result(
            run_id, definition, as_of, "adapter returned mismatched run or strategy identity"
        )
    return result


def run_screening(
    registry: ScreeningRegistry,
    adapters: Mapping[str, StrategyAdapter],
    clock: Clock,
    *,
    strategy_ids: tuple[str, ...] | None = None,
) -> tuple[ScreeningResult, ...]:
    """Run every requested registered strategy independently and return one
    ScreeningResult per strategy, ordered deterministically by strategy_id.
    """
    requested = tuple(sorted(strategy_ids if strategy_ids is not None else registry.registered_ids()))
    definitions = []
    for strategy_id in requested:
        definition = registry.get(strategy_id)
        if strategy_id not in adapters:
            raise UnknownScreeningStrategyIdError(strategy_id)
        definitions.append(definition)

    as_of = clock.now()
    run_id = _compute_run_id(requested, as_of)
    return tuple(
        _run_one(run_id, definition, adapters[definition.strategy_id], clock, as_of)
        for definition in definitions
    )
