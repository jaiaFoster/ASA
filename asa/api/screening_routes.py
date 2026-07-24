"""GET /api/v1/capabilities, GET /api/v1/screening[/{signal}[/{symbol}]],
POST /api/v1/screening/{signal}/{symbol}/refresh (API-003, API-004,
SPRINT-008, cut over to strategy_runtime in SPRINT-009R/EPIC-R5).

Read endpoints call only strategy_runtime.service.get_state(), which
itself only ever reads through the injected LatestResultRepository and
never triggers a provider request (matching screening.service.get_state()'s
own guarantee before this cutover) -- proven at this layer too by
tests/asa/test_screening_routes.py, not merely inferred. The refresh
endpoint is the one deliberate exception: it calls
strategy_runtime.service.refresh() for exactly the one requested
signal/symbol pair, never a whole universe or a whole signal.

The public response shape (ScreeningResultResponse/RefreshResultResponse/
CapabilitiesResponse) is byte-for-byte unchanged by this cutover -- see
asa/api/screening_models.py's own from_universal_result() translation and
tests/asa/test_screening_engine_parity.py, which proves the legacy
screening.service-backed path and this strategy_runtime-backed path
produce an identical wire response for the same deterministic input.

/capabilities is deliberately NOT cut over: it serves static catalog
metadata (including manifest_id, which StrategyContract has no field for)
and executes nothing, so screening.registry.signal_catalog() remains its
data source -- see docs/strategy_runtime/legacy-runtime-deprecation-plan.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request

from asa.api.agent_models import agent_api_error
from asa.api.screening_models import (
    CapabilitiesResponse,
    RefreshResultResponse,
    ScreeningResultResponse,
    ScreeningResultsEnvelope,
    SignalCapabilityResponse,
)
from market_data import load_market_data_config_from_environment
from market_data.live_transport import build_live_transport
from screening.live_acquisition import APPROVED_LIVE_UNIVERSE, live_only_config
from screening.registry import ScreeningRegistry, signal_catalog
from strategy_runtime.market_data_planning import (
    build_shared_market_data_access,
    enabled_provider_configs,
)
from strategy_runtime.persistence import LatestResultRepository
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult
from strategy_runtime.service import get_state, refresh

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


@dataclass(frozen=True, slots=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _paginate(
    records: tuple[UniversalScreeningResult, ...], limit: int, offset: int
) -> tuple[tuple[UniversalScreeningResult, ...], int]:
    total = len(records)
    return records[offset : offset + limit], total


def build_screening_router(
    repository: LatestResultRepository,
    registry: StrategyRegistry[UniversalScreeningResult],
    authorize: Callable[[Request], None],
    transport_factory: Callable[[str], object] = build_live_transport,
    *,
    capabilities_registry: ScreeningRegistry,
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
                for definition in signal_catalog(capabilities_registry)
            ]
        )

    @router.get("/screening", response_model=ScreeningResultsEnvelope)
    def list_screening(
        limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
    ) -> ScreeningResultsEnvelope:
        records = get_state(repository)
        page, total = _paginate(records, limit, offset)
        return ScreeningResultsEnvelope(
            results=[ScreeningResultResponse.from_universal_result(item) for item in page],
            total=total,
            limit=limit,
            offset=offset,
        )

    @router.get("/screening/{signal}", response_model=ScreeningResultsEnvelope)
    def list_screening_for_signal(
        signal: str,
        limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
    ) -> ScreeningResultsEnvelope:
        _require_registered_signal(signal)
        records = get_state(repository, strategy_id=signal)
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
        config = live_only_config(load_market_data_config_from_environment())
        if not enabled_provider_configs(config):
            raise agent_api_error(
                503,
                "NO_LIVE_PROVIDER_CONFIGURED",
                "No live market data provider is enabled for this deployment",
            )
        clock = _SystemClock()
        access = build_shared_market_data_access(config, transport_factory, clock, (symbol,))
        subject_access = access[symbol]
        result = refresh(
            registry,
            repository,
            clock,
            strategy_id=signal,
            symbol=symbol,
            fulfillment_by_subject={symbol: subject_access.fulfillment},
        )
        return RefreshResultResponse.from_universal_result(
            result, request_count=len(subject_access.budget_manager.accounting)
        )

    return router
