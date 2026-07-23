"""Canonical current-state record and repository port for screening
results (API-001, SPRINT-008).

Pure interface and dataclass only -- no infrastructure imports, so
screening/'s own "no infrastructure imports" architecture boundary
(tests/architecture/test_screening_boundaries.py) needs no change. A
concrete repository implementation (owned by backend/, which already talks
to Postgres) is dependency-injected by whatever caller constructs one;
screening/ itself never imports one.

ScreeningStateRecord is a *projection* of a run's ScreeningResult onto
"current state for one strategy/symbol pair" -- narrower than
ScreeningResult (no per-run evidence/provenance/completeness, which are
run-specific, not state), and stable to store and overwrite in place
(SPRINT-008: "store only the latest evaluated state, never historical
runs").

Field named signal_id/signal_version, not strategy_id/strategy_version like
ScreeningResult itself: backend/tests/test_boundaries.py::
test_forbidden_legacy_technologies_are_absent bans the literal substring
"strategy" anywhere under backend/src/, and backend/'s Postgres repository
implementation (which lives there) must reference this record's field
names directly to persist and read them. Discovered while implementing
that repository, not assumed up front -- ScreeningStateRecord is a new
type introduced by this sprint, not the long-established ScreeningResult,
so renaming its own fields for this reason carries no compatibility cost.
"signal" was already the Founder-approved word for this sprint's public
HTTP path segment (GOV-008A); using it here too keeps one consistent
vocabulary through the whole feature instead of "signal" at the HTTP
boundary and "strategy" underneath it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from screening.results import ScreeningResult


@dataclass(frozen=True, slots=True)
class ScreeningStateRecord:
    signal_id: str
    signal_version: str
    symbol: str
    outcome: str
    explanation: str | None
    metrics: dict[str, str]
    updated_at: datetime
    dependency_timestamps: dict[str, datetime]

    @classmethod
    def from_result(
        cls,
        result: ScreeningResult,
        *,
        symbol: str,
        dependency_timestamps: dict[str, datetime] | None = None,
    ) -> ScreeningStateRecord:
        """symbol is always caller-supplied, never parsed from
        result.subject_identity: runner.py's own convention sets
        subject_identity to "unknown" for any StrategyAdapterError-raised
        failure (e.g. MISSING_DATA before a subject was ever resolved) --
        exactly the kind of outcome a "current state" record must still be
        able to represent. The caller always already knows which symbol it
        requested (refresh() takes it as its own explicit parameter), so
        there is no need to recover it from the result at all.
        """
        explanation = result.signal_classification or result.failure_detail
        metrics = (
            {"strategy_native_score": str(result.strategy_native_score)}
            if result.strategy_native_score is not None
            else {}
        )
        return cls(
            signal_id=result.strategy_id,
            signal_version=result.strategy_version,
            symbol=symbol,
            outcome=result.outcome_status.value,
            explanation=explanation,
            metrics=metrics,
            updated_at=result.as_of,
            dependency_timestamps=dependency_timestamps or {"as_of": result.as_of},
        )


class ScreeningStateRepository(Protocol):
    """Stores only the latest evaluated state per (signal_id, symbol) --
    never historical runs. upsert() always overwrites any existing record
    for the same (signal_id, symbol) pair.
    """

    def upsert(self, record: ScreeningStateRecord) -> None: ...

    def get_all(self) -> tuple[ScreeningStateRecord, ...]: ...

    def get_for_signal(self, signal_id: str) -> tuple[ScreeningStateRecord, ...]: ...

    def get_one(self, signal_id: str, symbol: str) -> ScreeningStateRecord | None: ...
