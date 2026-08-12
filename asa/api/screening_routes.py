"""GET /api/v1/capabilities, GET /api/v1/screening[/{signal}[/{symbol}]],
POST /api/v1/screening/{signal}/{symbol}/refresh (API-003, API-004,
SPRINT-008, cut over to strategy_runtime in SPRINT-009R/EPIC-R5; cut over
to the shared subject-plan/shadow orchestration seam in SPRINT-014
S14-PR-05A).

Read endpoints call only strategy_runtime.service.get_state(), which
itself only ever reads through the injected LatestResultRepository and
never triggers a provider request -- proven at this layer too by
tests/asa/test_screening_routes.py, not merely inferred. The refresh
endpoint is the one deliberate exception: it calls
strategy_runtime.orchestration.refresh_with_shadow() for exactly the one
requested signal/symbol pair, never a whole universe or a whole signal.
Legacy stays authoritative and is the only result ever returned or
persisted here; a diagnostic-only shadow result is never exposed on this
public HTTP surface, only logged internally (see refresh_with_shadow's own
module for the full contract).

The capabilities endpoint is projected from the same universal contracts
the runtime executes. It has no separate legacy registry authority.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from asa.api.agent_models import agent_api_error
from asa.api.screening_models import (
    CapabilitiesResponse,
    OpportunityHistoryResponse,
    RefreshResultResponse,
    ScreeningResultResponse,
    ScreeningResultsEnvelope,
    SignalCapabilityResponse,
)
from domain import UnknownReason
from market_data import load_market_data_config_from_environment
from market_data.attempts import AcquisitionAttemptRepository
from market_data.live_transport import build_live_transport
from market_data.session_schedule import ON_DEMAND_COOLDOWN
from screening.cycle_identity import (
    manual_invocation_slot_id,
    new_screening_cycle_id,
    scope_identity,
)
from screening.live_acquisition import APPROVED_LIVE_UNIVERSE, live_only_config
from strategy_runtime.adapters import (
    build_migrated_cutover_policy,
    build_migrated_shadow_registry,
    build_migrated_strategy_registry,
    migrated_shadow_capability_reducers,
    migrated_shadow_resolution_policy,
)
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.lifecycle import RecommendedAction
from strategy_runtime.market_data_planning import (
    build_shared_market_data_access,
    enabled_provider_configs,
)
from strategy_runtime.orchestration import (
    build_subject_acquisition_access,
    prepare_subject_shadow_knowledge,
    refresh_with_shadow,
)
from strategy_runtime.persistence import (
    LatestResultRepository,
    ObservationHistoryRepository,
    replay_opportunity_history,
)
from strategy_runtime.preparation_diagnostics import classify_subject_preparation_exception
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import EvaluationState, UniversalScreeningResult
from strategy_runtime.service import get_state, record_opportunity_observation

DEFAULT_LIMIT = 100
MAX_LIMIT = 500
FRESHNESS_THRESHOLD_SECONDS = 86_400
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _FrozenRequestClock:
    """One fixed ``now``, captured once at the start of this on-demand
    refresh -- not a fresh wall-clock reading on every call (Architect
    checkpoint: seventeenth review, "the API root still constructs
    _SystemClock, then independently calls clock.now() when building the
    shadow registry, preparing shadow knowledge, generating the plan ID,
    executing legacy Earnings, and later generating the shadow
    diagnostic").

    Mirrors asa/scheduled_screening.py's own _FrozenCycleClock rationale
    (SPRINT-013 S13-03B): subject-first shadow preparation and legacy
    execution must construct byte-identical request-window timestamps
    (effective_start/effective_end embedded in every CapabilityRequest via
    MarketDataRequestContext) for the shared plan's own request-identity
    de-duplication to actually work -- an advancing clock silently defeats
    that, producing distinct CapabilityRequest objects for what should be
    the exact same demand, which can both miss the plan's cache and let
    parity comparisons report a false temporal mismatch (legacy's own
    result.observed_at differs from the shadow's own sealed-snapshot
    as_of purely because of clock drift, not real evidence disagreement).
    """

    value: datetime

    def now(self) -> datetime:
        return self.value


def _paginate(
    records: tuple[UniversalScreeningResult, ...], limit: int, offset: int
) -> tuple[tuple[UniversalScreeningResult, ...], int]:
    total = len(records)
    return records[offset : offset + limit], total


def _filter_and_sort(
    records: tuple[UniversalScreeningResult, ...],
    *,
    signal: str | None,
    symbol: str | None,
    outcome: str | None,
    lifecycle_stage: str | None,
    freshness: Literal["fresh", "stale"] | None,
    status: str | None,
    sort_by: str | None,
    sort_order: Literal["asc", "desc"],
) -> tuple[UniversalScreeningResult, ...]:
    now = datetime.now(UTC)
    selected = tuple(
        item
        for item in records
        if (signal is None or item.strategy_id == signal)
        and (symbol is None or item.symbol == symbol)
        and (outcome is None or _OUTCOME_FILTER_VALUES[item.evaluation_state] == outcome)
        and (lifecycle_stage is None or item.lifecycle_stage == lifecycle_stage)
        and (status is None or item.recommendation_state == status)
        and (
            freshness is None
            or (
                (
                    "fresh"
                    if item.temporal.usability_status in {"usable", "usable_with_warning"}
                    else "stale"
                )
                if item.temporal is not None
                else (
                    "fresh"
                    if max(0, int((now - item.observed_at).total_seconds()))
                    <= FRESHNESS_THRESHOLD_SECONDS
                    else "stale"
                )
            )
            == freshness
        )
    )
    reverse = sort_order == "desc"
    if sort_by is None:
        return selected
    if sort_by == "observed_at":
        return tuple(
            sorted(
                selected,
                key=lambda item: (item.observed_at, item.strategy_id, item.symbol),
                reverse=reverse,
            )
        )
    if sort_by == "age_seconds":
        return tuple(
            sorted(
                selected,
                key=lambda item: (
                    max(0, int((now - item.observed_at).total_seconds())),
                    item.strategy_id,
                    item.symbol,
                ),
                reverse=reverse,
            )
        )
    if sort_by.startswith("metrics."):
        metric_name = sort_by.removeprefix("metrics.")
        if not metric_name:
            raise agent_api_error(422, "INVALID_SORT", "Metric sort requires a metric name")
        numeric: list[tuple[Decimal, UniversalScreeningResult]] = []
        missing: list[UniversalScreeningResult] = []
        for item in selected:
            value = item.metrics.get(metric_name)
            if value is None:
                missing.append(item)
                continue
            native = value.native()
            if isinstance(native, bool) or not isinstance(native, (int, Decimal)):
                raise agent_api_error(
                    422,
                    "NON_NUMERIC_SORT_METRIC",
                    f"Metric {metric_name!r} is not numeric",
                )
            numeric.append((Decimal(native), item))
        numeric.sort(
            key=lambda pair: (pair[0], pair[1].strategy_id, pair[1].symbol),
            reverse=reverse,
        )
        missing.sort(key=lambda item: (item.strategy_id, item.symbol))
        return tuple(item for _, item in numeric) + tuple(missing)
    raise agent_api_error(
        422,
        "INVALID_SORT",
        "sort_by must be observed_at, age_seconds, or metrics.<name>",
    )


_OUTCOME_FILTER_VALUES = {
    EvaluationState.PASS: "pass",
    EvaluationState.NO_SIGNAL: "no_signal",
    EvaluationState.MISSING_DATA: "missing_data",
    EvaluationState.MALFORMED_OUTPUT: "malformed_output",
    EvaluationState.ADAPTER_EXCEPTION: "strategy_exception",
}


def build_screening_router(
    repository: LatestResultRepository,
    registry: StrategyRegistry[UniversalScreeningResult],
    authorize: Callable[[Request], None],
    transport_factory: Callable[[str], object] = build_live_transport,
    *,
    capabilities_catalog: tuple[SignalCatalogEntry, ...],
    history_repository: ObservationHistoryRepository,
    acquisition_attempt_repository: AcquisitionAttemptRepository,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(authorize)])

    def _require_registered_signal(signal: str) -> None:
        if not registry.is_registered(signal):
            raise agent_api_error(404, "UNKNOWN_SIGNAL", f"No registered signal {signal!r}")

    @router.get("/capabilities", response_model=CapabilitiesResponse)
    def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(
            signals=[
                SignalCapabilityResponse.from_definition(definition)
                for definition in capabilities_catalog
            ]
        )

    @router.get("/screening", response_model=ScreeningResultsEnvelope)
    def list_screening(
        limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
        signal: str | None = None,
        symbol: str | None = None,
        outcome: str | None = None,
        lifecycle_stage: str | None = None,
        freshness: Literal["fresh", "stale"] | None = None,
        status: str | None = None,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> ScreeningResultsEnvelope:
        records = _filter_and_sort(
            get_state(repository),
            signal=signal,
            symbol=symbol,
            outcome=outcome,
            lifecycle_stage=lifecycle_stage,
            freshness=freshness,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        page, total = _paginate(records, limit, offset)
        return ScreeningResultsEnvelope(
            results=[ScreeningResultResponse.from_universal_result(item) for item in page],
            total=total,
            limit=limit,
            offset=offset,
        )

    @router.get(
        "/screening/opportunities/{opportunity_id}/history",
        response_model=OpportunityHistoryResponse,
    )
    def opportunity_history(
        opportunity_id: str,
        limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
    ) -> OpportunityHistoryResponse:
        history = replay_opportunity_history(history_repository, opportunity_id)
        if history is None:
            raise agent_api_error(
                404,
                "NO_OPPORTUNITY_HISTORY",
                f"No opportunity history for {opportunity_id!r}",
            )
        return OpportunityHistoryResponse.from_history(history, limit=limit, offset=offset)

    @router.get("/screening/{signal}", response_model=ScreeningResultsEnvelope)
    def list_screening_for_signal(
        signal: str,
        limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
        symbol: str | None = None,
        outcome: str | None = None,
        lifecycle_stage: str | None = None,
        freshness: Literal["fresh", "stale"] | None = None,
        status: str | None = None,
        sort_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> ScreeningResultsEnvelope:
        _require_registered_signal(signal)
        records = _filter_and_sort(
            get_state(repository, strategy_id=signal),
            signal=None,
            symbol=symbol,
            outcome=outcome,
            lifecycle_stage=lifecycle_stage,
            freshness=freshness,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        page, total = _paginate(records, limit, offset)
        return ScreeningResultsEnvelope(
            results=[ScreeningResultResponse.from_universal_result(item) for item in page],
            total=total,
            limit=limit,
            offset=offset,
        )

    @router.get("/screening/{signal}/{symbol}", response_model=ScreeningResultResponse)
    def get_screening_result(signal: str, symbol: str) -> ScreeningResultResponse:
        _require_registered_signal(signal)
        records = get_state(repository, strategy_id=signal, symbol=symbol)
        if not records:
            raise agent_api_error(
                404, "NO_SCREENING_RESULT", f"No screening result for {signal!r}/{symbol!r}"
            )
        return ScreeningResultResponse.from_universal_result(records[0])

    @router.post(
        "/screening/{signal}/{symbol}/refresh",
        response_model=RefreshResultResponse,
    )
    def refresh_screening_result(signal: str, symbol: str) -> RefreshResultResponse:
        _require_registered_signal(signal)
        if symbol not in APPROVED_LIVE_UNIVERSE:
            raise agent_api_error(
                422,
                "UNSUPPORTED_SYMBOL",
                f"Refresh is bounded to the approved live universe {APPROVED_LIVE_UNIVERSE}, "
                f"not {symbol!r}",
            )
        clock = _FrozenRequestClock(datetime.now(UTC))
        prior = repository.get_one(signal, symbol)
        if (
            prior is not None
            and prior.temporal is not None
            and clock.now() - prior.temporal.last_refresh_attempt_at < ON_DEMAND_COOLDOWN
        ):
            return RefreshResultResponse.from_universal_result(
                prior.to_result(),
                request_count=0,
                provider_contacted=False,
                result_changed=False,
                refresh_failed=False,
            )
        config = live_only_config(load_market_data_config_from_environment())
        if not enabled_provider_configs(config):
            raise agent_api_error(
                503,
                "NO_LIVE_PROVIDER_CONFIGURED",
                "No live market data provider is enabled for this deployment",
            )
        access = build_shared_market_data_access(config, transport_factory, clock, (symbol,))
        subject_access = access[symbol]
        # One subject-owned plan acquires and seals all evidence before the
        # provider-blind strategy evaluation is constructed.
        acquisition = build_subject_acquisition_access(
            symbol,
            subject_access.fulfillment,
            attempt_repository=acquisition_attempt_repository,
            plan_id=new_screening_cycle_id(
                invocation_type="api_refresh",
                slot_id=manual_invocation_slot_id(clock.now()),
                scope_id=scope_identity(((signal, symbol),)),
            ),
            clock=clock,
        )
        subject_registry = build_migrated_strategy_registry()
        # Generic shadow-preparation seam (Architect checkpoint: sixteenth
        # review, "do not eagerly acquire shadow-only data for an
        # unshadowed API request ... shadow preparation must be limited to
        # shadowed strategies actually requested for that subject"):
        # prepared only when ``signal`` -- the one strategy this request is
        # actually evaluating -- itself has a registered shadow binding.
        # Never a hand-written `if signal == "earnings_calendar"` branch,
        # and never triggered merely because some other, unrequested
        # strategy happens to be registered for shadowing. A preparation
        # failure is isolated and never affects this request's own legacy
        # evaluation below.
        shadow_registry = build_migrated_shadow_registry(clock.now())
        # SPRINT-014 S14-PR-05, Architect checkpoint: nineteenth review,
        # "one shared cutover policy owner used identically by scheduled
        # and API roots" -- same function, same environment boundary as
        # asa/scheduled_screening.py's own call, never a route-specific
        # switch.
        cutover_policy = build_migrated_cutover_policy(os.environ)
        shadow_knowledge_by_subject: (
            dict[str, ReadOnlyStrategyInput[object] | UnknownReason] | None
        ) = None
        if signal in shadow_registry.strategy_ids():
            try:
                shadow_knowledge_by_subject = prepare_subject_shadow_knowledge(
                    acquisition.plan,
                    clock.now(),
                    shadow_registry,
                    subject=symbol,
                    provider_metadata=subject_access.provider_metadata,
                    resolution_policy_by_capability=migrated_shadow_resolution_policy(
                        subject_access.capability_registry, (signal,)
                    ),
                    capability_reducer_by_capability=migrated_shadow_capability_reducers(),
                    strategy_ids=(signal,),
                )
            except Exception as failure:
                _LOGGER.warning(
                    "shadow_subject_preparation_failed",
                    extra={
                        "signal_id": signal,
                        "symbol": symbol,
                        "failure_class": classify_subject_preparation_exception(failure),
                        "exception_type": type(failure).__name__,
                    },
                    exc_info=True,
                )
        try:
            result, shadow_diagnostic = refresh_with_shadow(
                subject_registry,
                repository,
                clock,
                strategy_id=signal,
                symbol=symbol,
                observations=tuple,
                shadow_registry=shadow_registry,
                shadow_knowledge_by_subject=shadow_knowledge_by_subject,
                cutover_policy=cutover_policy,
            )
        except RuntimeError:
            if prior is None:
                raise
            prior_result = prior.to_result()
            return RefreshResultResponse.from_universal_result(
                prior_result,
                request_count=len(subject_access.budget_manager.accounting),
                result_changed=False,
                refresh_failed=True,
            )
        if shadow_diagnostic is not None:
            # Diagnostic-only (Architect checkpoint: sixteenth review,
            # "log/record shadow diagnostics internally instead"): never
            # exposed on this public HTTP response, never persisted, never
            # affects the legacy result above -- safe, sanitized fields
            # only, no provider payloads.
            _LOGGER.info(
                "shadow_parity_diagnostic",
                extra={
                    "signal_id": signal,
                    "symbol": symbol,
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
                    subject_registry,
                    history_repository,
                    result,
                    recommended_action=RecommendedAction.NO_ACTION,
                )
            except Exception:
                # Latest state is already committed. History is additive and
                # must never corrupt or roll back the canonical latest result.
                _LOGGER.warning(
                    "opportunity history append failed",
                    extra={
                        "signal_id": result.strategy_id,
                        "symbol": result.symbol,
                        "opportunity_id": result.opportunity_id,
                    },
                )
        return RefreshResultResponse.from_universal_result(
            result,
            request_count=len(subject_access.budget_manager.accounting),
            result_changed=prior is None or prior.to_result() != result,
            refresh_failed=False,
        )

    return router
