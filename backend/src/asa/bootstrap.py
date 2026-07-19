from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from asa.api.routes import build_router
from asa.application.ports.quotes import QuoteProvider
from asa.application.ports.repositories import MarketObservationRepository
from asa.application.use_cases import MarketQuoteService
from asa.config import Settings
from asa.integrations.postgres import PostgresMarketObservationRepository, create_postgres_engine
from asa.integrations.providers.deterministic_fake import DeterministicFakeQuoteProvider
from asa.logging import configure_logging, request_id_context


@dataclass(frozen=True)
class DependencyOverrides:
    quote_provider: QuoteProvider | None = None
    repository: MarketObservationRepository | None = None
    engine_factory: Callable[[str], Engine] | None = None


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
    quote_service = MarketQuoteService(
        provider=provider,
        repository=repository,
        fresh_for=timedelta(seconds=settings.fresh_for_seconds),
    )

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
            return response
        finally:
            request_id_context.reset(token)

    app.state.dependencies = {
        "quote_provider": provider,
        "repository": repository,
        "quote_service": quote_service,
    }
    return app


def _build_provider(settings: Settings) -> QuoteProvider:
    if settings.quote_provider != "deterministic_fake":
        raise ValueError(f"unsupported quote provider: {settings.quote_provider}")
    return DeterministicFakeQuoteProvider()
