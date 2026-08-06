"""GET /api/v1/capabilities, GET /api/v1/screening[/{signal}[/{symbol}]],
POST /api/v1/screening/{signal}/{symbol}/refresh (API-003, API-004,
SPRINT-008, cut over to strategy_runtime in SPRINT-009R/EPIC-R5).

Read endpoints call only strategy_runtime.service.get_state(), which
itself only ever reads through the injected LatestResultRepository and
never triggers a provider request -- proven at this layer too by
tests/asa/test_screening_routes.py, not merely inferred. The refresh
endpoint is the one deliberate exception: it calls
strategy_runtime.service.refresh() for exactly the one requested
signal/symbol pair, never a whole universe or a whole signal.

The capabilities endpoint is projected from the same universal contracts
the runtime executes. It has no separate legacy registry authority.
"""

from __future__ import annotations

import logging
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
from market_data import load_market_data_config_from_environment
from market_data.attempts import AcquisitionAttemptRepository
from market_data.live_transport import build_live_transport
from market_data.session_schedule import ON_DEMAND_COOLDOWN
from market_data.subject_plan import SubjectAcquisitionPlan
from screening.live_acquisition import APPROVED_LIVE_UNIVERSE, live_only_config
from screening.sealed_earnings_calendar import (
    acquire_sealed_earnings_calendar_evidence,
    default_resolution_policy_by_capability,
)
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.lifecycle import RecommendedAction
from strategy_runtime.market_data_planning import (
    build_shared_market_data_access,
    enabled_provider_configs,
    provider_metadata_for,
)
from strategy_runtime.persistence import (
    LatestResultRepository,
    ObservationHistoryRepository,
    replay_opportunity_history,
)
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import EvaluationState, UniversalScreeningResult
from strategy_runtime.service import get_state, record_opportunity_observation, refresh

DEFAULT_LIMIT = 100
MAX_LIMIT = 500
FRESHNESS_THRESHOLD_SECONDS = 86_400
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


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
                    if item.temporal.usability_status
                    in {"usable", "usable_with_warning"}
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
        return OpportunityHistoryResponse.from_history(
            history, limit=limit, offset=offset
        )

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
        clock = _SystemClock()
        prior = repository.get_one(signal, symbol)
        if (
            prior is not None
            and prior.temporal is not None
            and clock.now() - prior.temporal.last_refresh_attempt_at
            < ON_DEMAND_COOLDOWN
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
        # SPRINT-014 S14-PR-05: registry is rebuilt per request (never
        # reused from the module-level one passed into this function,
        # which registered its own legacy composition binding with no
        # subject at all, at app startup, before any symbol was known) --
        # forward_factor/skew_momentum's own legacy binding closure needs
        # this exact request's subject_access.fulfillment to close over,
        # mirroring asa/scheduled_screening.py's own identical ordering.
        request_registry = build_migrated_strategy_registry(
            legacy_fulfillment_by_subject={symbol: subject_access.fulfillment}
        )
        sealed_evidence_by_subject = None
        if signal == "earnings_calendar":
            try:
                provider_metadata = provider_metadata_for(config, transport_factory, clock)
                plan = SubjectAcquisitionPlan(
                    symbol,
                    subject_access.fulfillment,
                    attempt_repository=acquisition_attempt_repository,
                    plan_id=f"on-demand-refresh:{signal}:{symbol}:{clock.now().isoformat()}",
                    clock=clock,
                )
                sealed_evidence = acquire_sealed_earnings_calendar_evidence(
                    symbol,
                    plan,
                    clock,
                    provider_metadata=provider_metadata,
                    resolution_policy_by_capability=default_resolution_policy_by_capability(
                        provider_metadata
                    ),
                )
                sealed_evidence_by_subject = {symbol: sealed_evidence}
            except Exception:
                # Same isolation as the scheduled path: a failure here
                # falls through to earnings_calendar_adapter's own
                # existing "requires sealed subject-first evidence"
                # handling, which strategy_runtime's generic per-adapter
                # exception boundary already converts into a graceful
                # ADAPTER_EXCEPTION result, not a 500.
                _LOGGER.warning(
                    "sealed earnings calendar evidence acquisition failed for "
                    "on-demand refresh",
                    extra={"signal_id": signal, "symbol": symbol},
                    exc_info=True,
                )
        try:
            result = refresh(
                request_registry,
                repository,
                clock,
                strategy_id=signal,
                symbol=symbol,
                fulfillment_by_subject={symbol: subject_access.fulfillment},
                sealed_evidence_by_subject=sealed_evidence_by_subject,
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
        if result.opportunity_id is not None:
            try:
                record_opportunity_observation(
                    request_registry,
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
