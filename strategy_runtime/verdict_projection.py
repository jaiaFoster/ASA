"""Generic graph-verdict to evaluation-state projection (SP-01E).

The shared projection every graph-verdict adapter uses (the PCS and Skew
Momentum adapters are migrated here; three-state adapters must use it).
UNKNOWN projects to MISSING_DATA and is never folded into NO_SIGNAL or FAIL.
The verdict string itself is carried unchanged on the result.
"""

from __future__ import annotations

from strategy_runtime.result import EvaluationState

_STATES = {
    "PASS": EvaluationState.PASS,
    "WATCH": EvaluationState.PASS,
    "FAIL": EvaluationState.NO_SIGNAL,
    "UNKNOWN": EvaluationState.MISSING_DATA,
}


def evaluation_state_for_verdict(verdict: str) -> EvaluationState:
    try:
        return _STATES[verdict]
    except KeyError:
        raise ValueError(f"unsupported graph verdict: {verdict!r}") from None


def unknown_gate_blockers(gate_results: tuple[tuple[str, bool | None], ...]) -> tuple[str, ...]:
    """Typed blockers for every gate whose three-state value is UNKNOWN."""
    return tuple(
        f"typed unknown gate: {name}" for name, value in sorted(gate_results) if value is None
    )
