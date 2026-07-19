from fastapi import APIRouter, HTTPException, Request, status

from asa.api.models import HealthResponse, IngestQuotesRequest, IngestQuotesResponse, QuoteResponse
from asa.application.ports.repositories import MarketObservationRepository
from asa.application.use_cases import MarketQuoteService


def build_router(
    quote_service: MarketQuoteService,
    repository: MarketObservationRepository,
    development_ingest_enabled: bool,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.get("/readiness", response_model=HealthResponse)
    def readiness() -> HealthResponse:
        if not repository.check_health():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            )
        return HealthResponse(status="ready")

    @router.post("/market/quotes/ingest", response_model=IngestQuotesResponse)
    def ingest_quotes(payload: IngestQuotesRequest, request: Request) -> IngestQuotesResponse:
        if not development_ingest_enabled:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        observations = quote_service.ingest_quotes(payload.symbols)
        if not observations:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="no supported symbols",
            )
        request.state.provider_request_id = observations[0].provenance.provider_request_id
        return IngestQuotesResponse(
            observations=[QuoteResponse.from_domain(item) for item in observations]
        )

    @router.get(
        "/market/quotes/{symbol}",
        response_model=QuoteResponse,
        operation_id="getLatestQuote",
    )
    def latest_quote(symbol: str) -> QuoteResponse:
        observation = quote_service.get_latest_quote(symbol)
        if observation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="quote unavailable")
        return QuoteResponse.from_domain(observation)

    return router
