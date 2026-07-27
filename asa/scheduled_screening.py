"""SPRINT-008D/PROD-002: scheduled production screening execution
(cut over to strategy_runtime in SPRINT-009R/EPIC-R5).

Calls strategy_runtime.service.refresh() -- the same shared execution graph
POST /api/v1/screening/{signal}/{symbol}/refresh already calls (both, in
turn, run the exact same unmodified screening execution graph internally
via strategy_runtime.adapters._screening_bridge) -- once per (signal,
symbol) pair in the production screening universe
(project/reports/SPRINT-008D-SCREENING-UNIVERSE.md), persisting through
the real PostgresLatestResultRepository (universal_screening_state). No
signal-selection or acquisition logic is reimplemented here.

This must write to the same table asa/api/screening_routes.py now reads
from -- writing anywhere else would silently starve the API of fresh data
after this cutover.

Not a background daemon: this module has no loop, no in-process scheduler,
no timer. It runs the full universe once per invocation and exits.
Scheduling -- how often this runs -- is deliberately kept external (a
Railway Cron Schedule or any equivalent externally-triggered invocation),
per this sprint's own architecture_principles.

Usage: python -m asa.scheduled_screening [--json]
Exit code: 0 if every pair completed without an unexpected exception (any
isolated per-signal failure outcome, e.g. missing data, is still a
completed, persisted result, not a failure of this runner); 1 if any
pair raised an exception this runner had to isolate.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from asa.config import Settings
from asa.integrations.observation_history_postgres import PostgresObservationHistoryRepository
from asa.integrations.postgres import create_postgres_engine
from asa.integrations.refresh_schedule_postgres import (
    PostgresRefreshScheduleClaimRepository,
)
from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from market_data import load_market_data_config_from_environment
from market_data.live_transport import build_live_transport
from market_data.session_schedule import SessionRefreshSchedule
from screening import APPROVED_LIVE_UNIVERSE, EARNINGS_CALENDAR_UNIVERSE
from screening.live_acquisition import live_only_config
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.lifecycle import RecommendedAction
from strategy_runtime.market_data_planning import (
    build_shared_market_data_access,
    enabled_provider_configs,
)
from strategy_runtime.persistence import LatestResultRepository, ObservationHistoryRepository
from strategy_runtime.service import record_opportunity_observation, refresh

# The production screening universe (project/reports/SPRINT-008D-SCREENING-
# UNIVERSE.md, PROD-001; expanded SPRINT-011/UNI-001-UNI-002): all three
# migrated strategies now run in scheduled production. forward_factor and
# skew_momentum, whose data requirements are met entirely by Tradier, run
# across the full APPROVED_LIVE_UNIVERSE; earnings_calendar, which needs an
# earnings event, runs only across EARNINGS_CALENDAR_UNIVERSE (the
# single-name subset -- ETFs have no earnings). Both source tuples are
# referenced directly, never copied, so this can't silently drift out of
# sync with the same bound asa/api/screening_routes.py and screening/cli.py's
# own --live flag already enforce (PROD-005 confirmed this pattern
# explicitly; SPRINT-010's REL-001 fixed earnings_calendar's own live
# acquisition, the reason it was excluded here before).
PRODUCTION_SCREENING_UNIVERSE: tuple[tuple[str, str], ...] = tuple(
    (signal_id, symbol)
    for signal_id in ("forward_factor", "skew_momentum")
    for symbol in APPROVED_LIVE_UNIVERSE
) + tuple(("earnings_calendar", symbol) for symbol in EARNINGS_CALENDAR_UNIVERSE)
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class PairOutcome:
    signal_id: str
    symbol: str
    outcome: str | None
    request_count: int | None
    error: str | None


class RefreshScheduleClaimRepository(Protocol):
    def claim(self, slot_id: str, claimed_at: datetime) -> bool: ...


def run_scheduled_refresh(
    universe: tuple[tuple[str, str], ...] = PRODUCTION_SCREENING_UNIVERSE,
    *,
    repository: LatestResultRepository | None = None,
    history_repository: ObservationHistoryRepository | None = None,
    transport_factory: Callable[[str], object] = build_live_transport,
    claim_repository: RefreshScheduleClaimRepository | None = None,
    enforce_schedule: bool = False,
    now: datetime | None = None,
) -> tuple[PairOutcome, ...]:
    """Run one bounded refresh per pair in ``universe``, in order,
    persisting every result. One pair's failure never stops the others --
    a fresh CapabilityFulfillmentService (and its own request budget) is
    built per pair, exactly matching the per-request pattern
    asa/api/screening_routes.py already uses, never shared or cached
    across pairs.

    ``repository`` and ``transport_factory`` are injectable (default:
    the real Postgres repository and the real live transport) so this
    function is directly testable without a live database or network,
    the same DependencyOverrides-style pattern asa/bootstrap.py already
    uses.
    """
    run_at = now or datetime.now(UTC)
    if enforce_schedule:
        slot = SessionRefreshSchedule().due_slot(run_at)
        if slot is None:
            return ()
        resolved_claim_repository = claim_repository or (
            PostgresRefreshScheduleClaimRepository(
                create_postgres_engine(Settings().database_url)
            )
        )
        if not resolved_claim_repository.claim(slot.slot_id, run_at):
            return ()

    resolved_repository = repository or PostgresLatestResultRepository(
        create_postgres_engine(Settings().database_url)
    )
    resolved_history_repository = history_repository or PostgresObservationHistoryRepository(
        create_postgres_engine(Settings().database_url)
    )
    registry = build_migrated_strategy_registry()
    config = live_only_config(load_market_data_config_from_environment())
    if not enabled_provider_configs(config):
        raise RuntimeError(
            "scheduled refresh requires at least one enabled live market data "
            "provider; none are enabled"
        )
    clock = _SystemClock()
    outcomes: list[PairOutcome] = []
    for signal_id, symbol in universe:
        access = build_shared_market_data_access(config, transport_factory, clock, (symbol,))
        subject_access = access[symbol]
        try:
            result = refresh(
                registry,
                resolved_repository,
                clock,
                strategy_id=signal_id,
                symbol=symbol,
                fulfillment_by_subject={symbol: subject_access.fulfillment},
            )
            if result.opportunity_id is not None:
                try:
                    record_opportunity_observation(
                        registry,
                        resolved_history_repository,
                        result,
                        recommended_action=RecommendedAction.NO_ACTION,
                    )
                except Exception:
                    _LOGGER.warning(
                        "scheduled opportunity history append failed",
                        extra={
                            "signal_id": result.strategy_id,
                            "symbol": result.symbol,
                            "opportunity_id": result.opportunity_id,
                        },
                    )
            outcomes.append(
                PairOutcome(
                    signal_id,
                    symbol,
                    result.evaluation_state.value,
                    len(subject_access.budget_manager.accounting),
                    None,
                )
            )
        except Exception as exc:
            outcomes.append(PairOutcome(signal_id, symbol, None, None, str(exc)))
    return tuple(outcomes)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m asa.scheduled_screening",
        description="Run one bounded refresh per pair in the production screening universe.",
    )
    parser.add_argument("--json", action="store_true", help="Emit only machine-readable JSON.")
    args = parser.parse_args(argv)

    outcomes = run_scheduled_refresh(enforce_schedule=True)
    failures = [item for item in outcomes if item.error is not None]
    outcome_counts: dict[str, int] = {}
    for item in outcomes:
        key = "infrastructure_failure" if item.error is not None else (item.outcome or "unknown")
        outcome_counts[key] = outcome_counts.get(key, 0) + 1

    if not args.json:
        print(f"SCHEDULED SCREENING RUN -- {len(outcomes)} pairs")
        for item in outcomes:
            if item.error is not None:
                print(f"  {item.signal_id:<18} {item.symbol:<6} FAILED: {item.error}")
            else:
                print(
                    f"  {item.signal_id:<18} {item.symbol:<6} {item.outcome} "
                    f"(requests={item.request_count})"
                )
        print(f"  outcome counts: {outcome_counts}")

    print(
        json.dumps(
            {
                "total": len(outcomes),
                "failed": len(failures),
                # Sanitized outcome-distribution counts only (no symbols, no
                # request bodies) -- SPRINT-011/UNI-002's own safe
                # operational diagnostic, distinguishing legitimate
                # no_signal/pass outcomes from real infrastructure failures
                # at a glance, without exposing anything secret.
                "outcome_counts": outcome_counts,
                "results": [
                    {
                        "signal_id": item.signal_id,
                        "symbol": item.symbol,
                        "outcome": item.outcome,
                        "request_count": item.request_count,
                        "error": item.error,
                    }
                    for item in outcomes
                ],
            }
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
