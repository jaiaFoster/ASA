"""GET /api/v1/capabilities, GET /api/v1/screening[/{signal}[/{symbol}]]
(API-003, SPRINT-008).

Read-only: every handler here calls only screening.service.get_state(),
which itself only ever reads through the injected repository and never
triggers a provider request (screening/service.py's own documented
guarantee) -- proven at this layer too by
tests/asa/test_screening_routes.py, not merely inferred from get_state()'s
own docstring.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Query, Request

from asa.api.agent_models import agent_api_error
from asa.api.screening_models import (
    CapabilitiesResponse,
    ScreeningResultResponse,
    ScreeningResultsEnvelope,
    SignalCapabilityResponse,
)
from screening.registry import ScreeningRegistry, signal_catalog
from screening.service import get_state
from screening.state import ScreeningStateRecord, ScreeningStateRepository

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def _paginate(
    records: tuple[ScreeningStateRecord, ...], limit: int, offset: int
) -> tuple[tuple[ScreeningStateRecord, ...], int]:
    total = len(records)
    return records[offset : offset + limit], total


def build_screening_router(
    repository: ScreeningStateRepository,
    registry: ScreeningRegistry,
    authorize: Callable[[Request], None],
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

    return router
