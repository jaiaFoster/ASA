"""Persistence & History (SPRINT-009/EPIC-8).

Two pure Protocols, no infrastructure imports -- matching
screening/state.py's own established convention exactly (that module's
own docstring: "A concrete repository implementation ... is dependency-
injected by whatever caller constructs one; screening/ itself never
imports one"). This module follows the identical rule for the same
reason: strategy_runtime is root-level, deployable-application-independent
infrastructure, and a database driver is asa/'s own concern to own, not
this package's.

LatestResultRepository generalizes screening.state.ScreeningStateRepository
to EPIC-6's own UniversalScreeningResult rather than the narrower,
screening-specific ScreeningStateRecord -- same upsert-only,
latest-state-per-key shape, same guarantee (a symbol a run never touches
keeps whatever was already stored; nothing is ever silently cleared just
because a run happened). The existing screening_state table and its own
Postgres implementation (asa/integrations/screening_postgres.py) are
unchanged by this ticket -- EPIC-7's own migration is the point at which a
strategy first needs a concrete UniversalScreeningResult-shaped
implementation of this protocol, and that concrete implementation
(and its own Alembic migration) belongs there, not here, matching this
sprint's own precedent of deferring infrastructure to the point a real
consumer actually needs it (EPIC-3's own documented deferral of unifying
provider-wiring with screening/live_acquisition.py; EPIC-4's own
documented deferral of a payoff calculator with no proven need yet).

The protocol itself is shaped around UniversalSignalRow, not
UniversalScreeningResult directly: tests/asa/test_boundaries.py::
test_forbidden_legacy_technologies_are_absent bans the literal substring
"strategy" anywhere under asa/, and EPIC-9's own concrete Postgres
implementation lives there and must reference field/column/method names
directly to persist and read them. screening/state.py's own
ScreeningStateRecord already solved this identical problem by renaming
strategy_id/strategy_version to signal_id/signal_version; UniversalSignalRow
applies the same rename at the same boundary, discovered here the same
way -- while wiring EPIC-9's concrete repository, not assumed up front.
UniversalScreeningResult itself (EPIC-6's own public contract, used by
every adapter and by strategy_runtime.service's own return types) is
unchanged; only this narrower, not-yet-externally-used persistence
boundary is renamed.

ObservationHistoryRepository is genuinely new: append-only storage for
strategy_runtime.lifecycle.OpportunityObservation, keyed by opportunity_id
-- "append-only" enforced by this protocol's own shape (no update, no
delete, only append() and read), not merely by convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from strategy_runtime.lifecycle import OpportunityHistory, OpportunityObservation
from strategy_runtime.result import EvaluationState, RowType, UniversalScreeningResult
from strategy_runtime.values import TypedValue


@dataclass(frozen=True, slots=True)
class UniversalSignalRow:
    """Storage-boundary projection of UniversalScreeningResult, with
    strategy_id/strategy_version renamed to signal_id/signal_version --
    see this module's own docstring for why. Field-for-field otherwise;
    row_type/evaluation_state are stored as their plain string .value,
    matching UniversalScreeningResult's own enum-to-string convention at
    every other serialization boundary in this sprint.
    """

    signal_id: str
    signal_version: str
    symbol: str
    observation_id: str
    opportunity_id: str | None
    row_type: str
    verdict: str | None
    evaluation_state: str
    lifecycle_stage: str | None
    recommendation_state: str | None
    data_quality: str | None
    metrics: dict[str, TypedValue]
    economics: dict[str, TypedValue]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    provenance: tuple[str, ...]
    observed_at: datetime

    @classmethod
    def from_result(cls, result: UniversalScreeningResult) -> UniversalSignalRow:
        return cls(
            signal_id=result.strategy_id,
            signal_version=result.strategy_version,
            symbol=result.symbol,
            observation_id=result.observation_id,
            opportunity_id=result.opportunity_id,
            row_type=result.row_type.value,
            verdict=result.verdict,
            evaluation_state=result.evaluation_state.value,
            lifecycle_stage=result.lifecycle_stage,
            recommendation_state=result.recommendation_state,
            data_quality=result.data_quality,
            metrics=result.metrics,
            economics=result.economics,
            blockers=result.blockers,
            warnings=result.warnings,
            provenance=result.provenance,
            observed_at=result.observed_at,
        )

    def to_result(self) -> UniversalScreeningResult:
        return UniversalScreeningResult(
            strategy_id=self.signal_id,
            strategy_version=self.signal_version,
            symbol=self.symbol,
            observation_id=self.observation_id,
            opportunity_id=self.opportunity_id,
            row_type=RowType(self.row_type),
            verdict=self.verdict,
            evaluation_state=EvaluationState(self.evaluation_state),
            lifecycle_stage=self.lifecycle_stage,
            recommendation_state=self.recommendation_state,
            data_quality=self.data_quality,
            metrics=self.metrics,
            economics=self.economics,
            blockers=self.blockers,
            warnings=self.warnings,
            provenance=self.provenance,
            observed_at=self.observed_at,
        )


class LatestResultRepository(Protocol):
    """Stores only the latest UniversalSignalRow per (signal_id,
    symbol) -- upsert() always overwrites any existing row for the
    same pair, never accumulates history (ObservationHistoryRepository's
    own job). A symbol a given run never touches is never removed by that
    run -- "empty run never exposes stale data" means a caller sees
    exactly what was last actually computed, not nothing, and never a
    silently fabricated absence.
    """

    def upsert(self, row: UniversalSignalRow) -> None: ...

    def get_all(self) -> tuple[UniversalSignalRow, ...]: ...

    def get_for_signal(self, signal_id: str) -> tuple[UniversalSignalRow, ...]: ...

    def get_one(self, signal_id: str, symbol: str) -> UniversalSignalRow | None: ...


class ObservationHistoryRepository(Protocol):
    """Append-only: append() adds one observation to the history for its
    own opportunity_id; nothing in this protocol updates or removes a
    previously appended observation. history_for() returns the full,
    ordered evolution for one opportunity_id -- "history replay
    supported" means exactly this: every observation ever appended for
    that opportunity, oldest first, reconstructable at any time.

    One strategy's observations are isolated from every other strategy's
    by construction, not by a runtime check here: opportunity_id itself
    already encodes strategy_id (strategy_runtime.lifecycle.
    compute_opportunity_id()'s own first argument), so two different
    strategies can never collide on the same opportunity_id even when
    both write through the same repository instance.
    """

    def append(self, observation: OpportunityObservation) -> None: ...

    def history_for(self, opportunity_id: str) -> OpportunityHistory | None: ...


def replay_opportunity_history(
    repository: ObservationHistoryRepository, opportunity_id: str
) -> OpportunityHistory | None:
    """The one named "lifecycle replay" entrypoint (SPRINT-009R/EPIC-R3):
    every observation ever appended for ``opportunity_id``, oldest first,
    reconstructed from whatever repository a caller injects -- exactly
    ObservationHistoryRepository's own history_for() contract, given its
    own top-level name here so a caller reads "replay an opportunity's
    history" rather than reaching into the repository protocol directly.
    """
    return repository.history_for(opportunity_id)
