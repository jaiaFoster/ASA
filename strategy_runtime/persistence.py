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

ObservationHistoryRepository is genuinely new: append-only storage for
strategy_runtime.lifecycle.OpportunityObservation, keyed by opportunity_id
-- "append-only" enforced by this protocol's own shape (no update, no
delete, only append() and read), not merely by convention.
"""

from __future__ import annotations

from typing import Protocol

from strategy_runtime.lifecycle import OpportunityHistory, OpportunityObservation
from strategy_runtime.result import UniversalScreeningResult


class LatestResultRepository(Protocol):
    """Stores only the latest UniversalScreeningResult per (strategy_id,
    symbol) -- upsert() always overwrites any existing result for the
    same pair, never accumulates history (ObservationHistoryRepository's
    own job). A symbol a given run never touches is never removed by that
    run -- "empty run never exposes stale data" means a caller sees
    exactly what was last actually computed, not nothing, and never a
    silently fabricated absence.
    """

    def upsert(self, result: UniversalScreeningResult) -> None: ...

    def get_all(self) -> tuple[UniversalScreeningResult, ...]: ...

    def get_for_strategy(self, strategy_id: str) -> tuple[UniversalScreeningResult, ...]: ...

    def get_one(self, strategy_id: str, symbol: str) -> UniversalScreeningResult | None: ...


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
