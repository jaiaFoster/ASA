from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from asa.api.agent_auth import build_agent_authorizer
from asa.api.routes import build_router
from asa.api.screening_routes import build_screening_router
from asa.application.portfolio_use_cases import (
    PublishedPortfolioQuery,
    RunPortfolioIntelligence,
    RunQueryService,
)
from asa.application.ports.brokers import BrokerPortfolioProvider
from asa.application.ports.quotes import QuoteProvider
from asa.application.ports.repositories import MarketObservationRepository
from asa.application.ports.runs import RunPublicationRepository
from asa.application.use_cases import MarketQuoteService
from asa.config import Settings
from asa.integrations.postgres import PostgresMarketObservationRepository, create_postgres_engine
from asa.integrations.providers.deterministic_fake import DeterministicFakeQuoteProvider
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from asa.integrations.providers.robinhood import RobinhoodPortfolioProvider
from asa.integrations.runs_postgres import PostgresRunPublicationRepository
from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from asa.logging import configure_logging, request_id_context
from asa.market_data_ops.routes import build_operations_router
from market_data.live_transport import build_live_transport as build_transport_for_provider
from screening import SIGNAL_REGISTRY
from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.persistence import LatestResultRepository


@dataclass(frozen=True)
class DependencyOverrides:
    quote_provider: QuoteProvider | None = None
    repository: MarketObservationRepository | None = None
    run_repository: RunPublicationRepository | None = None
    broker_provider: BrokerPortfolioProvider | None = None
    engine_factory: Callable[[str], Engine] | None = None
    market_data_transport_factory: Callable[[str], object] | None = None
    screening_state_repository: LatestResultRepository | None = None


def build_application(
    settings: Settings,
    overrides: DependencyOverrides | None = None,
) -> FastAPI:
    """The single production composition root."""
    configure_logging()
    selected = overrides or DependencyOverrides()
    engine_factory = selected.engine_factory or create_postgres_engine
    repository = selected.repository or PostgresMarketObservationRepository(
        engine_factory(settings.database_url)
    )
    provider = selected.quote_provider or _build_provider(settings)
    run_repository = selected.run_repository or PostgresRunPublicationRepository(
        engine_factory(settings.database_url)
    )
    broker_provider = selected.broker_provider or _build_broker_provider(settings)
    screening_state_repository = (
        selected.screening_state_repository
        or PostgresLatestResultRepository(engine_factory(settings.database_url))
    )
    screening_registry = build_migrated_strategy_registry()
    agent_authorize = build_agent_authorizer(settings.agent_api_token)
    quote_service = MarketQuoteService(
        provider=provider,
        repository=repository,
        fresh_for=timedelta(seconds=settings.fresh_for_seconds),
    )
    portfolio_runner = RunPortfolioIntelligence(broker_provider, run_repository)
    portfolio_query = PublishedPortfolioQuery(
        run_repository,
        timedelta(seconds=settings.portfolio_fresh_for_seconds),
    )
    run_query = RunQueryService(run_repository)

    app = FastAPI(title="ASA Market Quote API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.include_router(
        build_router(
            quote_service=quote_service,
            repository=repository,
            development_ingest_enabled=settings.environment == "development",
            portfolio_runner=portfolio_runner,
            portfolio_query=portfolio_query,
            run_query=run_query,
        )
    )
    app.include_router(
        build_operations_router(
            settings.operations_token,
            selected.market_data_transport_factory or build_transport_for_provider,
            max_runs_per_hour=None if settings.environment == "development" else 50,
        )
    )
    app.include_router(
        build_screening_router(
            screening_state_repository,
            screening_registry,
            agent_authorize,
            selected.market_data_transport_factory or build_transport_for_provider,
            capabilities_registry=SIGNAL_REGISTRY,
        )
    )

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            # Explicit API version negotiation (SPRINT-008): every response
            # names the API version it was served by, so a caller can
            # confirm which contract it's talking to. Future versions get
            # their own /api/v2 prefix (URL-path versioning, matching the
            # existing /api/v1 convention) rather than a header switch.
            response.headers["API-Version"] = "v1"
            return response
        finally:
            request_id_context.reset(token)

    app.state.dependencies = {
        "quote_provider": provider,
        "repository": repository,
        "quote_service": quote_service,
        "run_repository": run_repository,
        "broker_provider": broker_provider,
        "portfolio_runner": portfolio_runner,
        "portfolio_query": portfolio_query,
        "screening_state_repository": screening_state_repository,
        "agent_authorize": agent_authorize,
    }
    return app


def _build_provider(settings: Settings) -> QuoteProvider:
    if settings.quote_provider != "deterministic_fake":
        raise ValueError(f"unsupported quote provider: {settings.quote_provider}")
    return DeterministicFakeQuoteProvider()


def _build_broker_provider(settings: Settings) -> BrokerPortfolioProvider:
    if settings.broker_portfolio_provider == "deterministic_fake_broker":
        return DeterministicFakeBrokerPortfolioProvider()
    if settings.broker_portfolio_provider == "robinhood":
        if settings.robinhood_username is None or settings.robinhood_password is None:
            raise ValueError("Robinhood provider credentials are unavailable")
        return RobinhoodPortfolioProvider(
            username=settings.robinhood_username.get_secret_value(),
            password=settings.robinhood_password.get_secret_value(),
            totp_secret=(
                None
                if settings.robinhood_totp_secret is None
                else settings.robinhood_totp_secret.get_secret_value()
            ),
            account_numbers=settings.selected_robinhood_accounts,
        )
    raise ValueError(f"unsupported broker portfolio provider: {settings.broker_portfolio_provider}")
