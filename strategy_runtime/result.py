"""Universal Screening Result (SPRINT-009/EPIC-6).

One canonical result envelope every strategy emits, regardless of what
that strategy evaluates. Generalizes screening.results.ScreeningResult's
own outcome_status/signal_classification split -- evaluation_state and
verdict here play the same two roles (execution-level outcome vs. a
strategy's own business classification) -- and adds the lifecycle/
opportunity/recommendation fields ScreeningResult never needed, since no
currently-shipped strategy tracks lifecycle. That is EPIC-5's own
generalization target; this module defines the envelope shape only, not
how a lifecycle-aware strategy populates it.

Strategy-specific data belongs only inside metrics and economics -- this
sprint's own EPIC-6 acceptance criterion ("strategy-specific data
contained within metrics/economics namespaces") is enforced structurally:
this envelope has no strategy-named field anywhere, only these two open,
string-keyed namespaces every strategy writes its own values into.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


def compute_observation_id(run_id: str, strategy_id: str, symbol: str) -> str:
    """Deterministic identity for one (run, strategy, symbol) observation
    -- reproducible for identical inputs, matching the same sha256-hash
    convention screening/runner.py's own run_id and
    strategy_runtime.execution's own run_id already use, rather than a
    random UUID that would make two independently-computed observations
    of the identical run impossible to compare or deduplicate.
    """
    payload = {"run_id": run_id, "strategy_id": strategy_id, "symbol": symbol}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _normalized_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner}.{field_name} must be non-empty normalized text")


def _require_tz_aware(value: datetime, owner: str, field_name: str) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{owner}.{field_name} must be timezone-aware")


class RowType(str, Enum):
    """A single strategy's own evaluation produces exactly one RESULT row
    today -- every currently-shipped and every EPIC-7 migration-target
    strategy. Left open (not a bare bool) so a future strategy that emits
    more than one row per observation (e.g. one row per option leg) has
    somewhere to declare that without a new envelope field.
    """

    RESULT = "result"


class EvaluationState(str, Enum):
    """Generalizes screening.results.ScreeningOutcomeStatus -- the
    execution-level outcome for one (strategy, subject) evaluation,
    independent of the strategy's own business verdict. ADAPTER_EXCEPTION
    matches strategy_runtime.execution.ExecutionStatus's own vocabulary
    for the same concept (an unhandled adapter exception), not
    screening's older STRATEGY_EXCEPTION name -- one consistent name
    within this package rather than two for the same thing.
    """

    PASS = "pass"
    NO_SIGNAL = "no_signal"
    MISSING_DATA = "missing_data"
    MALFORMED_OUTPUT = "malformed_output"
    ADAPTER_EXCEPTION = "adapter_exception"


SUCCESS_EVALUATION_STATES = frozenset({EvaluationState.PASS, EvaluationState.NO_SIGNAL})


@dataclass(frozen=True, slots=True)
class UniversalScreeningResult:
    strategy_id: str
    strategy_version: str
    symbol: str
    observation_id: str
    opportunity_id: str | None
    row_type: RowType
    verdict: str | None
    evaluation_state: EvaluationState
    lifecycle_stage: str | None
    recommendation_state: str | None
    data_quality: str | None
    metrics: dict[str, str]
    economics: dict[str, str]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    provenance: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        for name in ("strategy_id", "strategy_version", "symbol", "observation_id"):
            _normalized_text(getattr(self, name), "UniversalScreeningResult", name)
        _require_tz_aware(self.observed_at, "UniversalScreeningResult", "observed_at")

        is_success = self.evaluation_state in SUCCESS_EVALUATION_STATES
        if is_success:
            if self.verdict is None:
                raise ValueError(
                    "UniversalScreeningResult requires verdict for a successful evaluation_state"
                )
        elif self.verdict is not None:
            raise ValueError(
                "UniversalScreeningResult must not carry verdict for a non-success "
                "evaluation_state"
            )
        if self.verdict is not None:
            _normalized_text(self.verdict, "UniversalScreeningResult", "verdict")

        if (self.opportunity_id is None) != (self.lifecycle_stage is None):
            raise ValueError(
                "UniversalScreeningResult.opportunity_id and lifecycle_stage must both be "
                "present or both be absent -- a lifecycle stage with no tracked opportunity, "
                "or an opportunity with no stage, is not a valid state"
            )
        if self.opportunity_id is not None:
            _normalized_text(self.opportunity_id, "UniversalScreeningResult", "opportunity_id")
        if self.lifecycle_stage is not None:
            _normalized_text(self.lifecycle_stage, "UniversalScreeningResult", "lifecycle_stage")
        if self.recommendation_state is not None:
            _normalized_text(
                self.recommendation_state, "UniversalScreeningResult", "recommendation_state"
            )
        if self.data_quality is not None:
            _normalized_text(self.data_quality, "UniversalScreeningResult", "data_quality")
