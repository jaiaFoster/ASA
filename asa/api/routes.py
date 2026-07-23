from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from asa.api.models import (
    HealthResponse,
    IngestQuotesRequest,
    IngestQuotesResponse,
    PortfolioEnvelope,
    PositionsEnvelope,
    QuoteResponse,
    RunResponse,
    StartRunRequest,
)
from asa.application.portfolio_use_cases import (
    PublishedPortfolioQuery,
    RunPortfolioIntelligence,
    RunQueryService,
)
from asa.application.ports.repositories import MarketObservationRepository
from asa.application.use_cases import MarketQuoteService


def build_router(
    quote_service: MarketQuoteService,
    repository: MarketObservationRepository,
    development_ingest_enabled: bool,
    portfolio_runner: RunPortfolioIntelligence,
    portfolio_query: PublishedPortfolioQuery,
    run_query: RunQueryService,
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

    @router.post("/runs", response_model=RunResponse)
    def start_run(payload: StartRunRequest) -> RunResponse:
        result = portfolio_runner.execute(
            payload.requested_at,
            payload.release_sha,
            payload.effective_config_hash,
        )
        run = run_query.get(result.run_id)
        if run is None:
            raise HTTPException(status_code=500, detail="persisted run unavailable")
        return RunResponse.from_domain(run, run_query.publication_for(run.id))

    @router.get("/runs/current", response_model=RunResponse)
    def current_run() -> RunResponse:
        run = run_query.latest()
        if run is None:
            raise HTTPException(status_code=404, detail="run unavailable")
        return RunResponse.from_domain(run, run_query.publication_for(run.id))

    @router.get("/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: UUID) -> RunResponse:
        run = run_query.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run unavailable")
        return RunResponse.from_domain(run, run_query.publication_for(run.id))

    @router.get("/portfolio", response_model=PortfolioEnvelope, operation_id="getPortfolio")
    def get_portfolio() -> PortfolioEnvelope:
        view = portfolio_query.current()
        if view is None:
            raise HTTPException(status_code=404, detail="portfolio unavailable")
        return PortfolioEnvelope.from_view(view)

    @router.get("/positions", response_model=PositionsEnvelope, operation_id="getPositions")
    def get_positions() -> PositionsEnvelope:
        view = portfolio_query.current()
        if view is None:
            raise HTTPException(status_code=404, detail="positions unavailable")
        return PositionsEnvelope.from_view(view)

    return router
