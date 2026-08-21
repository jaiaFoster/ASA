from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from asa.integrations.observation_history_postgres import PostgresObservationHistoryRepository
from asa.integrations.postgres import PostgresMarketObservationRepository, create_postgres_engine
from asa.integrations.providers.deterministic_fake import DeterministicFakeQuoteProvider
from asa.integrations.providers.deterministic_fake_broker import (
    DeterministicFakeBrokerPortfolioProvider,
)
from asa.integrations.providers.robinhood import RobinhoodPortfolioProvider
from asa.integrations.refresh_schedule_postgres import PostgresSubjectRefreshRepository
from asa.integrations.runs_postgres import PostgresRunPublicationRepository
from asa.integrations.screening_acquisition_attempts_postgres import (
    PostgresAcquisitionAttemptRepository,
)
from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository
from asa.logging import configure_logging, request_id_context
from asa.market_data_ops.routes import build_operations_router
from asa.ui import mount_ui
from market_data.attempts import AcquisitionAttemptRepository
from market_data.live_transport import build_live_transport as build_transport_for_provider
from strategy_runtime.adapters import (
    build_migrated_signal_catalog,
    build_migrated_strategy_registry,
)
from strategy_runtime.persistence import LatestResultRepository, ObservationHistoryRepository

API_VERSION = "v1"


@dataclass(frozen=True)
class DependencyOverrides:
    quote_provider: QuoteProvider | None = None
    repository: MarketObservationRepository | None = None
    run_repository: RunPublicationRepository | None = None
    broker_provider: BrokerPortfolioProvider | None = None
    engine_factory: Callable[[str], Engine] | None = None
    market_data_transport_factory: Callable[[str], object] | None = None
    latest_result_repository: LatestResultRepository | None = None
    observation_history_repository: ObservationHistoryRepository | None = None
    acquisition_attempt_repository: AcquisitionAttemptRepository | None = None
    screening_operational_health: Callable[[], dict[str, object]] | None = None


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
    latest_result_repository = selected.latest_result_repository or PostgresLatestResultRepository(
        engine_factory(settings.database_url)
    )
    # Contract/membership registry only. Production evaluation is composed
    # from prepared read-only knowledge at the request boundary.
    screening_registry = build_migrated_strategy_registry()
    observation_history_repository = (
        selected.observation_history_repository
        or PostgresObservationHistoryRepository(engine_factory(settings.database_url))
    )
    acquisition_attempt_repository = (
        selected.acquisition_attempt_repository
        or PostgresAcquisitionAttemptRepository(engine_factory(settings.database_url))
    )
    subject_refresh_repository = PostgresSubjectRefreshRepository(
        engine_factory(settings.database_url)
    )

    def postgres_screening_operational_health() -> dict[str, object]:
        health = subject_refresh_repository.operational_health(as_of=datetime.now(UTC))
        return {
            "last_attempted_batch_at": health.last_attempted_batch_at,
            "last_successful_batch_at": health.last_successful_batch_at,
            "oldest_subject_age": health.oldest_subject_age_seconds,
            "overdue_subject_count": health.overdue_subject_count,
            "last_batch_subject_count": health.last_batch_subject_count,
            "last_batch_pair_count": health.last_batch_pair_count,
            "last_batch_failure_count": health.last_batch_failure_count,
            "last_batch_incomplete_diagnostic_count": (
                health.last_batch_incomplete_diagnostic_count
            ),
        }

    screening_operational_health = (
        selected.screening_operational_health or postgres_screening_operational_health
    )
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

    app = FastAPI(title="ASA Market Quote API", version=settings.application_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.include_router(
        build_router(
            quote_service=quote_service,
            repository=repository,
            development_ingest_enabled=settings.environment == "development",
            portfolio_runner=portfolio_runner,
            portfolio_query=portfolio_query,
            run_query=run_query,
            application_version=settings.application_version,
            api_version=API_VERSION,
            release_sha=settings.release_sha,
        )
    )
    app.include_router(
        build_operations_router(
            settings.operations_token,
            selected.market_data_transport_factory or build_transport_for_provider,
            max_runs_per_hour=None if settings.environment == "development" else 50,
            acquisition_attempt_repository=acquisition_attempt_repository,
        )
    )
    app.include_router(
        build_screening_router(
            latest_result_repository,
            screening_registry,
            agent_authorize,
            selected.market_data_transport_factory or build_transport_for_provider,
            capabilities_catalog=build_migrated_signal_catalog(),
            history_repository=observation_history_repository,
            acquisition_attempt_repository=acquisition_attempt_repository,
            operational_health=screening_operational_health,
        )
    )
    mount_ui(app)

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
            response.headers["API-Version"] = API_VERSION
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
        "latest_result_repository": latest_result_repository,
        "observation_history_repository": observation_history_repository,
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
