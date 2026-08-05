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
from asa.integrations.screening_acquisition_attempts_postgres import (
    PostgresAcquisitionAttemptRepository,
)
from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from market_data import ReuseDecision, load_market_data_config_from_environment
from market_data.attempts import AcquisitionAttemptRepository, attempt_records_for
from market_data.live_transport import build_live_transport
from market_data.session_schedule import SessionRefreshSchedule
from screening import APPROVED_LIVE_UNIVERSE, EARNINGS_CALENDAR_UNIVERSE
from screening.cycle_identity import (
    manual_invocation_slot_id,
    new_screening_cycle_id,
    scope_identity,
)
from screening.cycle_identity import (
    pair_evaluation_id as compute_pair_evaluation_id,
)
from screening.live_acquisition import live_only_config
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.lifecycle import RecommendedAction
from strategy_runtime.market_data_planning import (
    build_provider_rolling_window_tracker,
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
class _FrozenCycleClock:
    """SPRINT-013 S13-03B: one fixed ``now``, captured once at cycle
    start -- not a fresh wall-clock reading on every call.

    ``screening/live_adapters.py``'s own per-strategy adapters (unmodified
    by this ticket) each capture ``now = clock.now()`` once at the start of
    their own evaluation and build their point-in-time capability requests'
    (quote, option chain, expirations) ``effective_start``/``effective_end``
    from it. A clock that advances between pairs -- the previous
    ``_SystemClock``, a fresh ``datetime.now(UTC)`` reading every call --
    made every pair's own request window subtly unique even for the exact
    same symbol evaluated a heartbeat apart, which made cycle-scoped reuse
    a no-op in practice for these capabilities: confirmed empirically while
    testing this fix (a same-symbol, same-strategy pair run twice back to
    back still needed a fresh quote/chain fetch the second time, because
    its request window's timestamps did not match the first's byte for
    byte), not assumed from reading the code alone.

    Market data's own observation timestamps (``effective_time``,
    freshness, provenance) always come from the provider's real response
    data, never from this clock, so freezing it does not change what
    "fresh" means for any observation -- only how this system itself
    timestamps "the moment this cycle looked," which is one coherent
    instant for every pair in one cycle, not 82 almost-identical ones
    scattered across however long the cycle actually took to run.
    """

    value: datetime

    def now(self) -> datetime:
        return self.value


@dataclass(frozen=True, slots=True)
class PairOutcome:
    signal_id: str
    symbol: str
    outcome: str | None
    request_count: int | None
    error: str | None
    attempts_recorded: bool


class RefreshScheduleClaimRepository(Protocol):
    def claim(self, slot_id: str, claimed_at: datetime) -> bool: ...


def run_scheduled_refresh(
    universe: tuple[tuple[str, str], ...] = PRODUCTION_SCREENING_UNIVERSE,
    *,
    repository: LatestResultRepository | None = None,
    history_repository: ObservationHistoryRepository | None = None,
    acquisition_attempt_repository: AcquisitionAttemptRepository | None = None,
    transport_factory: Callable[[str], object] = build_live_transport,
    claim_repository: RefreshScheduleClaimRepository | None = None,
    enforce_schedule: bool = False,
    now: datetime | None = None,
) -> tuple[PairOutcome, ...]:
    """Run one bounded refresh per pair in ``universe``, in order,
    persisting every result. One pair's failure never stops the others.

    One CapabilityFulfillmentService (and its own request budget) is built
    per unique *subject* for the whole cycle (SPRINT-013 S13-03B) -- not
    per pair, and not one shared instance across every subject either
    (cross-symbol reuse stays impossible by construction). Every pair
    touching the same symbol shares that symbol's own service, so an exact
    duplicate capability request made by more than one strategy for that
    symbol is served once, from the service's own reuse-eligibility-checked
    cache, and consumes no additional provider request or rolling-window
    reservation. asa/api/screening_routes.py's single-pair on-demand
    refresh endpoint has no cycle to share across and is unaffected --
    still one fresh service per request there, correctly.

    ``repository``, ``transport_factory``, and ``acquisition_attempt_
    repository`` are injectable (default: the real Postgres repositories
    and the real live transport) so this function is directly testable
    without a live database or network, the same DependencyOverrides-style
    pattern asa/bootstrap.py already uses.

    One screening_cycle_id is minted once for the whole invocation
    (SPRINT-013 S13-02) -- deterministically, from (invocation_type,
    slot_id, scope_id), never from raw wall-clock alone
    (screening.cycle_identity.new_screening_cycle_id). Each pair gets its
    own pair_evaluation_id derived from that cycle. Attempt persistence is
    best-effort per pair: a persistence failure never aborts an otherwise-
    successful strategy evaluation, but PairOutcome.attempts_recorded is
    set False so acquisition accounting is never silently reported
    complete when it wasn't.
    """
    run_at = now or datetime.now(UTC)
    invocation_type = "manual"
    slot_id = manual_invocation_slot_id(run_at)
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
        invocation_type = "scheduled"
        slot_id = slot.slot_id

    resolved_repository = repository or PostgresLatestResultRepository(
        create_postgres_engine(Settings().database_url)
    )
    resolved_history_repository = history_repository or PostgresObservationHistoryRepository(
        create_postgres_engine(Settings().database_url)
    )
    resolved_acquisition_attempt_repository = (
        acquisition_attempt_repository
        or PostgresAcquisitionAttemptRepository(create_postgres_engine(Settings().database_url))
    )
    registry = build_migrated_strategy_registry()
    config = live_only_config(load_market_data_config_from_environment())
    if not enabled_provider_configs(config):
        raise RuntimeError(
            "scheduled refresh requires at least one enabled live market data "
            "provider; none are enabled"
        )
    clock = _FrozenCycleClock(datetime.now(UTC))
    screening_cycle_id = new_screening_cycle_id(
        invocation_type=invocation_type, slot_id=slot_id, scope_id=scope_identity(universe)
    )
    # Exactly one ProviderRollingWindowTracker per cycle -- minted here,
    # beside screening_cycle_id, and passed by reference into every pair's
    # own RequestBudgetManager below (SPRINT-013 S13-03A). Never rebuilt
    # per pair, never a module-global singleton: a fresh tracker for every
    # new invocation of this function, so a new scheduled cycle always
    # starts with fresh cycle-scoped window state.
    rolling_window, providers_without_declared_limit = build_provider_rolling_window_tracker(
        config, clock
    )
    if providers_without_declared_limit:
        _LOGGER.info(
            "no_declared_rolling_limit",
            extra={
                "screening_cycle_id": screening_cycle_id,
                "provider_ids": providers_without_declared_limit,
            },
        )
    # SPRINT-013 S13-03B: one SubjectMarketDataAccess per unique symbol,
    # built exactly once for the whole cycle -- never rebuilt per pair.
    # Every pair below looks up its own symbol's already-built access
    # instead of constructing a fresh, single-use CapabilityFulfillmentService
    # (which discarded that service's own request de-duplication, see
    # market_data/fulfillment.py, before this fix). No module-global cache:
    # ``access`` is a local built fresh on every call to this function, so a
    # new scheduled cycle always starts from empty cycle-scoped state.
    unique_symbols = tuple(sorted({symbol for _, symbol in universe}))
    access = build_shared_market_data_access(
        config, transport_factory, clock, unique_symbols, rolling_window=rolling_window
    )
    reuse_counts = {
        "provider_calls": 0,
        "reuse_hits": 0,
        "stale_cache_bypasses": 0,
        "incomplete_cache_bypasses": 0,
        "requests_not_eligible_for_reuse": 0,
    }
    outcomes: list[PairOutcome] = []
    for signal_id, symbol in universe:
        subject_access = access[symbol]
        pair_id = compute_pair_evaluation_id(screening_cycle_id, signal_id, symbol)
        try:
            # SPRINT-013 S13-03B: call_log and the budget manager's own
            # accounting are both sliced around this pair's own refresh()
            # so only what *this* pair's own evaluation actually triggered
            # is ever persisted or counted for it -- neither completed_results
            # nor accounting's raw length can be used per pair any more once
            # the fulfillment service (and its budget manager) are shared
            # cycle-wide: both would include every other pair's own
            # contribution for this same subject, over- or double-counting
            # a shared symbol's request_count across the pairs that share it.
            call_log_start = len(subject_access.fulfillment.call_log)
            budget_accounting_start = len(subject_access.budget_manager.accounting)
            result = refresh(
                registry,
                resolved_repository,
                clock,
                strategy_id=signal_id,
                symbol=symbol,
                fulfillment_by_subject={symbol: subject_access.fulfillment},
            )
            pair_calls = subject_access.fulfillment.call_log[call_log_start:]
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
            attempts_recorded = True
            try:
                sequence_offset = 0
                for fulfillment_result, decision in pair_calls:
                    if decision is ReuseDecision.REUSED:
                        # SPRINT-013 S13-03B: a reuse hit consumed no
                        # provider request and produced no new attempt
                        # evidence -- never a fabricated attempt record for
                        # it, only this safe cycle-level count (required
                        # behavior: "do not create fake provider-attempt
                        # records for cache hits").
                        reuse_counts["reuse_hits"] += 1
                        continue
                    reuse_counts["provider_calls"] += 1
                    if decision is ReuseDecision.FRESH_AFTER_STALE_BYPASS:
                        reuse_counts["stale_cache_bypasses"] += 1
                    elif decision is ReuseDecision.FRESH_AFTER_INCOMPLETE_BYPASS:
                        reuse_counts["incomplete_cache_bypasses"] += 1
                    elif decision is ReuseDecision.FRESH_AFTER_OTHER_BYPASS:
                        reuse_counts["requests_not_eligible_for_reuse"] += 1
                    records = attempt_records_for(
                        fulfillment_result,
                        screening_cycle_id=screening_cycle_id,
                        pair_evaluation_id=pair_id,
                        recorded_at=clock.now(),
                        sequence_offset=sequence_offset,
                    )
                    sequence_offset += len(records)
                    resolved_acquisition_attempt_repository.record(records)
            except Exception:
                attempts_recorded = False
                _LOGGER.warning(
                    "scheduled acquisition attempt recording failed -- "
                    "diagnostics incomplete for this pair",
                    extra={
                        "signal_id": signal_id,
                        "symbol": symbol,
                        "screening_cycle_id": screening_cycle_id,
                        "pair_evaluation_id": pair_id,
                    },
                )
            outcomes.append(
                PairOutcome(
                    signal_id,
                    symbol,
                    result.evaluation_state.value,
                    len(subject_access.budget_manager.accounting) - budget_accounting_start,
                    None,
                    attempts_recorded,
                )
            )
        except Exception as exc:
            outcomes.append(PairOutcome(signal_id, symbol, None, None, str(exc), False))
    # Cycle-level sanitized accounting (SPRINT-013 S13-03A): provider_id ->
    # in-window reservation count only, no payloads, no per-pair detail.
    # This tracker is cycle-local and in-process -- it enforces truthfully
    # within this one invocation only, never across the separately
    # deployed always-on web service process or another concurrent
    # invocation of this same job (see project/reports/SPRINT-013-S13-03A-
    # wiring-notes.md's BLOCKED_DISTRIBUTED_QUOTA_OWNERSHIP packet).
    _LOGGER.info(
        "provider_rolling_window_summary",
        extra={"screening_cycle_id": screening_cycle_id, "summary": rolling_window.summary()},
    )
    # SPRINT-013 S13-03B: unique_capability_requests is the total number of
    # distinct (subject, capability, params, freshness) requests this
    # cycle ever resolved (fresh or bypassed-then-fresh), summed across
    # every subject's own fulfillment service -- reuse_hits above never
    # adds to this count, since a reuse resolves an already-counted request.
    unique_capability_requests = sum(
        len(item.fulfillment.completed_results) for item in access.values()
    )
    _LOGGER.info(
        "cycle_scoped_request_reuse_summary",
        extra={
            "screening_cycle_id": screening_cycle_id,
            "unique_capability_requests": unique_capability_requests,
            **reuse_counts,
        },
    )
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
    incomplete_diagnostics = [item for item in outcomes if not item.attempts_recorded]
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
                incomplete = "" if item.attempts_recorded else " [attempt diagnostics incomplete]"
                print(
                    f"  {item.signal_id:<18} {item.symbol:<6} {item.outcome} "
                    f"(requests={item.request_count}){incomplete}"
                )
        print(f"  outcome counts: {outcome_counts}")
        if incomplete_diagnostics:
            print(f"  attempt diagnostics incomplete for {len(incomplete_diagnostics)} pair(s)")

    print(
        json.dumps(
            {
                "total": len(outcomes),
                "failed": len(failures),
                # Never silently report complete acquisition accounting
                # (SPRINT-013 S13-02): a pair whose attempt persistence
                # failed is counted here even though its own screening
                # result may otherwise be a normal, non-failing outcome.
                "attempt_diagnostics_incomplete": len(incomplete_diagnostics),
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
                        "attempts_recorded": item.attempts_recorded,
                    }
                    for item in outcomes
                ],
            }
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
