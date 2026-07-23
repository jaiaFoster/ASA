"""GET /api/v1/capabilities, GET /api/v1/screening[/{signal}[/{symbol}]],
POST /api/v1/screening/{signal}/{symbol}/refresh (API-003, API-004,
SPRINT-008).

Read endpoints call only screening.service.get_state(), which itself only
ever reads through the injected repository and never triggers a provider
request (screening/service.py's own documented guarantee) -- proven at
this layer too by tests/asa/test_screening_routes.py, not merely inferred
from get_state()'s own docstring. The refresh endpoint is the one deliberate
exception: it calls screening.service.refresh() for exactly the one
requested signal/symbol pair, never a whole universe or a whole signal.
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
from screening.live_acquisition import (
    APPROVED_LIVE_UNIVERSE,
    build_fulfillment_service_with_accounting,
    enabled_provider_configs,
    live_only_config,
)
from screening.registry import ScreeningRegistry, signal_catalog
from screening.service import get_state, refresh
from screening.state import ScreeningStateRecord, ScreeningStateRepository

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


@dataclass(frozen=True, slots=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _paginate(
    records: tuple[ScreeningStateRecord, ...], limit: int, offset: int
) -> tuple[tuple[ScreeningStateRecord, ...], int]:
    total = len(records)
    return records[offset : offset + limit], total


def build_screening_router(
    repository: ScreeningStateRepository,
    registry: ScreeningRegistry,
    authorize: Callable[[Request], None],
    transport_factory: Callable[[str], object] = build_live_transport,
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
                for definition in signal_catalog(registry)
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
            results=[ScreeningResultResponse.from_record(item) for item in page],
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
        records = get_state(repository, signal_id=signal)
        page, total = _paginate(records, limit, offset)
        return ScreeningResultsEnvelope(
            results=[ScreeningResultResponse.from_record(item) for item in page],
            total=total,
            limit=limit,
            offset=offset,
        )

    @router.get("/screening/{signal}/{symbol}", response_model=ScreeningResultResponse)
    def get_screening_result(signal: str, symbol: str) -> ScreeningResultResponse:
        _require_registered_signal(signal)
        records = get_state(repository, signal_id=signal, symbol=symbol)
        if not records:
            raise agent_api_error(
                404, "NO_SCREENING_RESULT", f"No screening result for {signal!r}/{symbol!r}"
            )
        return ScreeningResultResponse.from_record(records[0])

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
        fulfillment, budget_manager = build_fulfillment_service_with_accounting(
            config, transport_factory, clock
        )
        record = refresh(
            repository, registry, fulfillment, clock, signal_id=signal, symbol=symbol
        )
        return RefreshResultResponse.from_record(
            record, request_count=len(budget_manager.accounting)
        )

    return router
