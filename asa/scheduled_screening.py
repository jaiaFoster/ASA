"""SPRINT-008D/PROD-002: scheduled production screening execution
(cut over to strategy_runtime in SPRINT-009R/EPIC-R5; cut over to the
shared subject-plan/shadow orchestration seam in SPRINT-014 S14-PR-05A).

Calls strategy_runtime.orchestration.refresh_with_shadow() -- the same
shared orchestration seam POST /api/v1/screening/{signal}/{symbol}/refresh
already calls (both, in turn, run the exact same unmodified screening
execution graph internally via strategy_runtime.adapters._screening_bridge)
-- once per (signal, symbol) pair in the production screening universe
(project/reports/SPRINT-008D-SCREENING-UNIVERSE.md), persisting through
the real PostgresLatestResultRepository (universal_screening_state). No
signal-selection or acquisition logic is reimplemented here. Legacy stays
authoritative: refresh_with_shadow()'s own second, diagnostic-only shadow
result is never persisted -- see its own module for the full contract.

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
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Protocol

from asa.config import Settings
from asa.integrations.historical_skew_postgres import PostgresHistoricalSkewRepository
from asa.integrations.observation_history_postgres import PostgresObservationHistoryRepository
from asa.integrations.postgres import create_postgres_engine
from asa.integrations.refresh_schedule_postgres import (
    PostgresRefreshScheduleClaimRepository,
    PostgresSubjectRefreshRepository,
)
from asa.integrations.screening_acquisition_attempts_postgres import (
    PostgresAcquisitionAttemptRepository,
)
from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from domain import CanonicalInstrumentIdentity, MarketObservation, UnknownReason
from market_data import ReuseDecision, load_market_data_config_from_environment
from market_data.attempts import AcquisitionAttemptRepository
from market_data.live_transport import build_live_transport
from market_data.session_schedule import ScheduledRefreshSlot, SessionRefreshSchedule
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
from screening.universe_cohorts import UniverseCohort, plan_universe_cohort
from screening.universe_membership import (
    SP500_MEMBERSHIP,
    EquityUniverseClassifications,
    canonical_equity_classifications,
)
from strategy_runtime.adapters import (
    build_migrated_cutover_policy,
    build_migrated_shadow_registry,
    build_migrated_strategy_registry,
    migrated_shadow_capability_reducers,
    migrated_shadow_resolution_policy,
)
from strategy_runtime.comparison_universe import (
    ASSET_TYPE_BY_INSTRUMENT,
    SECTOR_BY_INSTRUMENT,
)
from strategy_runtime.cross_subject_knowledge import compose_cross_subject_knowledge
from strategy_runtime.historical_evidence import HistoricalSkewRepository
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.lifecycle import RecommendedAction
from strategy_runtime.market_data_planning import (
    build_provider_rolling_window_tracker,
    build_shared_market_data_access,
    enabled_provider_configs,
)
from strategy_runtime.orchestration import (
    build_subject_acquisition_access,
    prepare_subject_shadow_knowledge_with_temporal,
    refresh_with_shadow,
)
from strategy_runtime.persistence import LatestResultRepository, ObservationHistoryRepository
from strategy_runtime.preparation_diagnostics import classify_subject_preparation_exception
from strategy_runtime.service import record_opportunity_observation

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

# UNI-01's current proven live capacity. Increasing this is a measured
# capacity decision, never a CLI/environment override.
SP500_COHORT_MAXIMUM_SUBJECTS = 30
_LOGGER = logging.getLogger(__name__)


def _cross_subject_classifications(symbols: tuple[str, ...]) -> EquityUniverseClassifications:
    """Authoritative S&P classifications plus explicit legacy-topology compatibility."""
    active = canonical_equity_classifications(SP500_MEMBERSHIP)
    asset_types = dict(active.asset_types)
    sectors = dict(active.sectors)
    for symbol in symbols:
        instrument = CanonicalInstrumentIdentity("symbol", symbol)
        if instrument in active.asset_types:
            continue
        legacy_asset_type = ASSET_TYPE_BY_INSTRUMENT.get(instrument)
        if legacy_asset_type is not None:
            asset_types[instrument] = legacy_asset_type
        legacy_sector = SECTOR_BY_INSTRUMENT.get(instrument)
        if legacy_sector is not None:
            sectors[instrument] = legacy_sector
    return EquityUniverseClassifications(
        MappingProxyType(asset_types), MappingProxyType(sectors)
    )


def _scheduled_cohort_ordinal(slot: ScheduledRefreshSlot) -> int:
    """Stable ordinal across every exchange-calendar refresh slot.

    Counting the schedule's actual slots (including holidays and early-close
    sessions) guarantees complete, gap-free cohort traversal without mutable
    scheduler state or a database cursor.
    """
    if slot.session_date < SP500_MEMBERSHIP.effective_date:
        raise ValueError("scheduled slot predates the active S&P 500 membership snapshot")
    schedule = SessionRefreshSchedule()
    cursor = SP500_MEMBERSHIP.effective_date
    ordinal = 0
    while cursor < slot.session_date:
        ordinal += len(schedule.slots_for(cursor))
        cursor += timedelta(days=1)
    session_slots = schedule.slots_for(slot.session_date)
    try:
        slot_offset = next(
            index for index, candidate in enumerate(session_slots) if candidate == slot
        )
    except StopIteration:
        raise ValueError("scheduled slot is not part of its session schedule") from None
    return ordinal + slot_offset


def scheduled_sp500_cohort(slot: ScheduledRefreshSlot) -> UniverseCohort:
    return plan_universe_cohort(
        SP500_MEMBERSHIP,
        maximum_subjects=SP500_COHORT_MAXIMUM_SUBJECTS,
        cohort_ordinal=_scheduled_cohort_ordinal(slot),
    )


def scheduled_sp500_universe(slot: ScheduledRefreshSlot) -> tuple[tuple[str, str], ...]:
    cohort = scheduled_sp500_cohort(slot)
    return tuple(
        (strategy_id, symbol)
        for symbol in cohort.symbols
        for strategy_id in ("forward_factor", "skew_momentum", "earnings_calendar")
    )


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
class _MonotonicUtcClock:
    """SPRINT-013 P0: a separate, genuinely advancing clock for
    ProviderRollingWindowTracker's own elapsed-window decisions --
    deliberately not the same instance as _FrozenCycleClock.

    Confirmed root cause this fixes: ProviderRollingWindowTracker.
    try_reserve() computes ``window_start = now - window_seconds`` from
    whatever clock it is given, to decide whether an earlier reservation
    has aged out of a provider's real rolling window. Given
    _FrozenCycleClock (correct and necessary for evaluation timestamps
    and cycle-scoped request-window identity/reuse, SPRINT-013 S13-03B),
    that ``now`` never advances during a cycle, so ``window_start`` never
    advances either -- once window_limit reservations land, none can
    ever prune, and a provider's real rolling rate limit silently
    becomes a hard per-cycle cap instead of the rolling window it is
    supposed to be.

    Anchored once at cycle start (``anchor_utc``/``anchor_monotonic``);
    every ``now()`` call projects forward by real elapsed monotonic time,
    never by re-reading the wall clock directly -- elapsed-window
    decisions must reflect true elapsed time, immune to a wall-clock
    adjustment (NTP step, DST) mid-cycle, which a raw ``datetime.now()``
    reading would not be. Still returns a genuine UTC ``datetime`` (not a
    raw monotonic float): ProviderRollingWindowTracker.apply_reset_hint()
    compares against provider-reported reset timestamps, which only ever
    exist in UTC wall-clock terms -- there is no monotonic equivalent of
    "resets at 14:32:00 UTC," so the clock's own output type must stay a
    real UTC datetime even though its own advancement is monotonic.
    """

    anchor_utc: datetime
    anchor_monotonic: float

    @classmethod
    def start(cls) -> _MonotonicUtcClock:
        return cls(datetime.now(UTC), time.monotonic())

    def now(self) -> datetime:
        elapsed_seconds = time.monotonic() - self.anchor_monotonic
        return self.anchor_utc + timedelta(seconds=elapsed_seconds)


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


class SubjectRefreshRepository(Protocol):
    def claim_oldest(
        self,
        subject_ids: Sequence[str],
        *,
        claimed_at: datetime,
        maximum_subjects: int,
        lease: timedelta,
    ) -> tuple[str, ...]: ...

    def complete(self, subject_id: str, *, completed_at: datetime, succeeded: bool) -> None: ...

    def batch_started(self, *, attempted_at: datetime, subject_count: int) -> None: ...

    def batch_completed(
        self,
        *,
        completed_at: datetime,
        pair_count: int,
        failure_count: int,
        incomplete_diagnostic_count: int,
    ) -> None: ...


def run_scheduled_refresh(
    universe: tuple[tuple[str, str], ...] | None = None,
    *,
    repository: LatestResultRepository | None = None,
    history_repository: ObservationHistoryRepository | None = None,
    acquisition_attempt_repository: AcquisitionAttemptRepository | None = None,
    historical_skew_repository: HistoricalSkewRepository | None = None,
    transport_factory: Callable[[str], object] = build_live_transport,
    claim_repository: RefreshScheduleClaimRepository | None = None,
    subject_refresh_repository: SubjectRefreshRepository | None = None,
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
    own pair_evaluation_id, used for shadow-diagnostic log correlation.

    Attempt persistence is now owned by each symbol's own
    SubjectAcquisitionPlan (SPRINT-014 S14-PR-05A), not recorded separately
    per pair here -- a persistence failure never aborts or corrupts an
    otherwise-successful strategy evaluation sharing that plan (the plan's
    own best-effort resilience, market_data.subject_plan.
    SubjectAcquisitionPlan.attempt_recording_degraded), but every
    PairOutcome sharing a degraded symbol's plan honestly reports
    attempts_recorded=False so acquisition accounting is never silently
    reported complete when it wasn't.
    """
    run_at = now or datetime.now(UTC)
    resolved_universe = PRODUCTION_SCREENING_UNIVERSE if universe is None else universe
    invocation_type = "manual"
    slot_id = manual_invocation_slot_id(run_at)
    if enforce_schedule:
        slot = SessionRefreshSchedule().due_slot(run_at)
        if slot is None:
            return ()
        invocation_type = "scheduled"
        slot_id = slot.slot_id
        if universe is None:
            resolved_subject_repository = subject_refresh_repository or (
                PostgresSubjectRefreshRepository(create_postgres_engine(Settings().database_url))
            )
            claimed_symbols = resolved_subject_repository.claim_oldest(
                SP500_MEMBERSHIP.symbols,
                claimed_at=run_at,
                maximum_subjects=SP500_COHORT_MAXIMUM_SUBJECTS,
                lease=timedelta(minutes=30),
            )
            if not claimed_symbols:
                return ()
            resolved_subject_repository.batch_started(
                attempted_at=run_at, subject_count=len(claimed_symbols)
            )
            resolved_universe = tuple(
                (strategy_id, symbol)
                for symbol in claimed_symbols
                for strategy_id in ("forward_factor", "skew_momentum", "earnings_calendar")
            )
            _LOGGER.info(
                "scheduled_oldest_subjects_selected",
                extra={
                    "universe_id": SP500_MEMBERSHIP.universe_id,
                    "source_revision_id": SP500_MEMBERSHIP.source_revision_id,
                    "subject_count": len(claimed_symbols),
                },
            )
        else:
            # Explicit/custom scheduled scopes retain delivery idempotency.
            # Production default scheduling uses atomic per-subject claims
            # instead, allowing overlapping cron processes to safely advance
            # disjoint portions of the stale backlog.
            resolved_claim_repository = claim_repository or (
                PostgresRefreshScheduleClaimRepository(
                    create_postgres_engine(Settings().database_url)
                )
            )
            if not resolved_claim_repository.claim(slot.slot_id, run_at):
                return ()
            resolved_subject_repository = None
    else:
        resolved_subject_repository = None

    universe = resolved_universe

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
    resolved_historical_skew_repository = (
        historical_skew_repository
        or PostgresHistoricalSkewRepository(create_postgres_engine(Settings().database_url))
    )
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
    #
    # SPRINT-013 P0: deliberately NOT `clock` (the frozen one). The
    # rolling-window tracker's own window-expiry arithmetic needs real
    # elapsed time to ever prune a reservation; `clock` must stay frozen
    # for evaluation timestamps and cycle-scoped request-window identity
    # (S13-03B) -- those are two different, independently correct
    # requirements on two different clocks, not one setting to tune.
    quota_clock = _MonotonicUtcClock.start()
    rolling_window, providers_without_declared_limit = build_provider_rolling_window_tracker(
        config, quota_clock
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
        config,
        transport_factory,
        clock,
        unique_symbols,
        budget_clock=quota_clock,
        rolling_window=rolling_window,
    )
    # One subject-owned plan per symbol acquires and seals shared evidence
    # before any provider-blind strategy evaluation is constructed.
    acquisition_access = {
        symbol: build_subject_acquisition_access(
            symbol,
            subject_access.fulfillment,
            attempt_repository=resolved_acquisition_attempt_repository,
            plan_id=f"{screening_cycle_id}:{symbol}",
            clock=clock,
        )
        for symbol, subject_access in access.items()
    }
    reuse_counts = {
        "provider_calls": 0,
        "reuse_hits": 0,
        "stale_cache_bypasses": 0,
        "incomplete_cache_bypasses": 0,
        "requests_not_eligible_for_reuse": 0,
    }

    def _tally_new_calls(symbol: str, call_log_start: int) -> None:
        # SPRINT-013 S13-03A/S13-03B sanitized reuse-accounting summary
        # (cycle_scoped_request_reuse_summary below): safe, no-payload
        # decision counts only -- called around every phase that can touch
        # a provider (shadow preparation below, and each pair's own
        # refresh_with_shadow() further down) so nothing this cycle ever
        # made falls outside the tally.
        for _fulfillment_result, decision in access[symbol].fulfillment.call_log[call_log_start:]:
            if decision is ReuseDecision.REUSED:
                # SPRINT-013 S13-03B: a reuse hit consumed no provider
                # request and produced no new attempt evidence -- never a
                # fabricated attempt record for it, only this safe
                # cycle-level count.
                reuse_counts["reuse_hits"] += 1
                continue
            reuse_counts["provider_calls"] += 1
            if decision is ReuseDecision.FRESH_AFTER_STALE_BYPASS:
                reuse_counts["stale_cache_bypasses"] += 1
            elif decision is ReuseDecision.FRESH_AFTER_INCOMPLETE_BYPASS:
                reuse_counts["incomplete_cache_bypasses"] += 1
            elif decision is ReuseDecision.FRESH_AFTER_OTHER_BYPASS:
                reuse_counts["requests_not_eligible_for_reuse"] += 1

    # Generic shadow-preparation seam (Architect checkpoint: fourteenth/
    # fifteenth/sixteenth review): shadow_registry is looked up generically
    # by strategy_id membership, never a hand-written
    # `if signal_id == "earnings_calendar"` branch -- today only Earnings
    # Calendar is registered. Prepared at most once per symbol, before any
    # pair sharing that symbol is evaluated below, and only for a symbol
    # whose own universe this cycle actually includes a shadowed strategy
    # -- never an eager shadow-only acquisition for a symbol that has none.
    # A preparation failure is isolated exactly like this module's other
    # best-effort side channels (skew capture, opportunity history) and
    # never aborts or affects any pair's own legacy evaluation.
    # Use the resolved repository, not only the optional injection argument.
    # In production the argument is normally ``None`` and the Postgres-backed
    # default above is the authoritative historical-evidence owner. Passing the
    # unresolved argument silently disabled Skew's historical z-score facts in
    # every default scheduled cycle.
    shadow_registry = build_migrated_shadow_registry(
        clock.now(), resolved_historical_skew_repository
    )
    shadow_capability_reducers = migrated_shadow_capability_reducers()
    # SPRINT-014 S14-PR-05, Architect checkpoint: nineteenth review, "one
    # shared cutover policy owner used identically by scheduled and API
    # roots" -- built once per cycle from the same environment boundary
    # market_data.config's own provider ASA_{PROVIDER}_ENABLED flags use,
    # never a route-specific switch.
    cutover_policy = build_migrated_cutover_policy(os.environ)
    requested_signal_ids_by_symbol: dict[str, set[str]] = {}
    for signal_id, symbol in universe:
        requested_signal_ids_by_symbol.setdefault(symbol, set()).add(signal_id)
    shadow_knowledge_by_symbol: dict[
        str, dict[str, ReadOnlyStrategyInput[object] | UnknownReason]
    ] = {}
    shadow_temporal_observations_by_symbol: dict[
        str, dict[str, tuple[MarketObservation, ...]]
    ] = {}
    prepared_request_count_by_symbol: dict[str, int] = {}
    for symbol in unique_symbols:
        if not (requested_signal_ids_by_symbol[symbol] & set(shadow_registry.strategy_ids())):
            continue
        call_log_start = len(access[symbol].fulfillment.call_log)
        budget_start = len(access[symbol].budget_manager.accounting)
        try:
            prepared_subject = prepare_subject_shadow_knowledge_with_temporal(
                acquisition_access[symbol].plan,
                clock.now(),
                shadow_registry,
                subject=symbol,
                provider_metadata=access[symbol].provider_metadata,
                resolution_policy_by_capability=migrated_shadow_resolution_policy(
                    access[symbol].capability_registry,
                    tuple(sorted(requested_signal_ids_by_symbol[symbol])),
                ),
                capability_reducer_by_capability=shadow_capability_reducers,
                strategy_ids=tuple(
                    sorted(
                        requested_signal_ids_by_symbol[symbol] & set(shadow_registry.strategy_ids())
                    )
                ),
            )
            shadow_knowledge_by_symbol[symbol] = dict(
                prepared_subject.knowledge_by_strategy
            )
            shadow_temporal_observations_by_symbol[symbol] = dict(
                prepared_subject.temporal_observations_by_strategy
            )
        except Exception as failure:
            _LOGGER.warning(
                "shadow_subject_preparation_failed",
                extra={
                    "symbol": symbol,
                    "screening_cycle_id": screening_cycle_id,
                    "failure_class": (classify_subject_preparation_exception(failure)),
                    "exception_type": type(failure).__name__,
                },
                exc_info=True,
            )
        finally:
            _tally_new_calls(symbol, call_log_start)
            prepared_request_count_by_symbol[symbol] = (
                len(access[symbol].budget_manager.accounting) - budget_start
            )
    # Provider-free cycle stage: all subject snapshots are sealed before
    # registered cross-subject families are materialized once and rebound to
    # their declaring consumers. This adds no acquisition and contains no
    # strategy identity branch.
    classifications = _cross_subject_classifications(unique_symbols)
    shadow_knowledge_by_symbol = compose_cross_subject_knowledge(
        shadow_knowledge_by_symbol,
        shadow_registry,
        asset_types=classifications.asset_types,
        sectors=classifications.sectors,
    ).knowledge_by_subject
    outcomes: list[PairOutcome] = []
    for signal_id, symbol in universe:
        subject_access = access[symbol]
        plan = acquisition_access[symbol].plan
        pair_id = compute_pair_evaluation_id(screening_cycle_id, signal_id, symbol)
        try:
            # SPRINT-013 S13-03B: the budget manager's own accounting is
            # sliced around this pair's own refresh_with_shadow() so only
            # what *this* pair's own evaluation actually triggered is ever
            # counted for it -- accounting's raw length can't be used per
            # pair once the fulfillment service (and its budget manager)
            # are shared cycle-wide: it would include every other pair's
            # own contribution for this same subject, over- or double-
            # counting a shared symbol's request_count across the pairs
            # that share it.
            budget_accounting_start = len(subject_access.budget_manager.accounting)
            call_log_start = len(subject_access.fulfillment.call_log)
            pair_registry = build_migrated_strategy_registry()

            def _subject_first_observations(
                symbol: str = symbol, signal_id: str = signal_id
            ) -> tuple[MarketObservation, ...]:
                return shadow_temporal_observations_by_symbol.get(symbol, {}).get(
                    signal_id, ()
                )

            result, shadow_diagnostic = refresh_with_shadow(
                pair_registry,
                resolved_repository,
                clock,
                strategy_id=signal_id,
                symbol=symbol,
                observations=tuple,
                subject_first_observations=_subject_first_observations,
                historical_skew_repository=resolved_historical_skew_repository,
                shadow_registry=shadow_registry,
                shadow_knowledge_by_subject=shadow_knowledge_by_symbol.get(symbol),
                cutover_policy=cutover_policy,
            )
            _tally_new_calls(symbol, call_log_start)
            if shadow_diagnostic is not None:
                # Diagnostic-only (Architect checkpoint: sixteenth review,
                # "log/record shadow diagnostics internally"): never
                # persisted, never affects the legacy result above -- safe,
                # sanitized fields only, no provider payloads.
                _LOGGER.info(
                    "shadow_parity_diagnostic",
                    extra={
                        "signal_id": signal_id,
                        "symbol": symbol,
                        "screening_cycle_id": screening_cycle_id,
                        "pair_evaluation_id": pair_id,
                        "shadow_status": shadow_diagnostic.status,
                        "shadow_mismatched_fields": shadow_diagnostic.mismatched_fields,
                        "shadow_unknown_code": shadow_diagnostic.shadow_unknown_code,
                        "shadow_unknown_demand_ids": shadow_diagnostic.shadow_unknown_demand_ids,
                        "shadow_snapshot_id": shadow_diagnostic.shadow_snapshot_id,
                        "shadow_snapshot_digest": shadow_diagnostic.shadow_snapshot_digest,
                    },
                )
            if result.opportunity_id is not None:
                try:
                    record_opportunity_observation(
                        pair_registry,
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
                        exc_info=True,
                    )
            # SPRINT-014 S14-PR-05A (Architect checkpoint: sixteenth
            # review): this module's own prior per-pair
            # attempt_records_for()/repository.record() block is retired.
            # acquisition_access[symbol].plan is now the single durable
            # attempt owner for every pair sharing this symbol -- it
            # persisted (or, on a real outage, best-effort logged and
            # flagged) every attempt already, inline, during this pair's
            # own refresh_with_shadow() call above. attempt_recording_
            # degraded is subject-scoped, not pair-scoped, exactly because
            # attempts themselves are now subject-scoped (shared across
            # every strategy that resolves the same request for this
            # symbol this cycle) -- every pair sharing a degraded symbol's
            # plan honestly reports the same incomplete-diagnostics signal.
            outcomes.append(
                PairOutcome(
                    signal_id,
                    symbol,
                    result.evaluation_state.value,
                    prepared_request_count_by_symbol.pop(symbol, 0)
                    + len(subject_access.budget_manager.accounting)
                    - budget_accounting_start,
                    None,
                    not plan.attempt_recording_degraded,
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
    if resolved_subject_repository is not None:
        completed_at = datetime.now(UTC)
        outcomes_by_subject = {
            symbol: tuple(item for item in outcomes if item.symbol == symbol)
            for symbol in unique_symbols
        }
        for symbol, subject_outcomes in outcomes_by_subject.items():
            resolved_subject_repository.complete(
                symbol,
                completed_at=completed_at,
                succeeded=bool(subject_outcomes)
                and all(item.error is None for item in subject_outcomes),
            )
        resolved_subject_repository.batch_completed(
            completed_at=completed_at,
            pair_count=len(outcomes),
            failure_count=sum(item.error is not None for item in outcomes),
            incomplete_diagnostic_count=sum(
                not item.attempts_recorded for item in outcomes
            ),
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
