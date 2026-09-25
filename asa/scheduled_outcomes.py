"""Run-and-exit forward-outcome collection (OUTCOME-INTELLIGENCE OI-03).

Invoked last from ``asa.scheduled_screening.main`` on the existing cron tick,
in its own isolated ``try`` -- no new cron, no daemon, and the screening
tick's JSON report is unchanged. Also runnable directly:
``python -m asa.scheduled_outcomes``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime

from asa.application.forward_outcomes import CollectionSummary, ForwardOutcomeCollector
from asa.config import Settings
from asa.integrations.forward_outcome_market_data import MarketDataOutcomeEvidenceSource
from asa.integrations.forward_outcome_postgres import PostgresForwardOutcomeRepository
from asa.integrations.portfolio_lifecycle_postgres import PostgresPortfolioLifecycleRepository
from asa.integrations.postgres import create_postgres_engine
from asa.integrations.proposal_enrollment_postgres import PostgresProposalEnrollmentRepository
from asa.integrations.screening_acquisition_attempts_postgres import (
    PostgresAcquisitionAttemptRepository,
)
from market_data import load_market_data_config_from_environment
from market_data.live_transport import build_live_transport
from screening.live_acquisition import live_only_config
from strategy_runtime.market_data_planning import enabled_provider_configs

_LOGGER = logging.getLogger(__name__)


def run_scheduled_outcome_collection(
    *,
    now: datetime | None = None,
    transport_factory: Callable[[str], object] = build_live_transport,
) -> CollectionSummary:
    config = live_only_config(load_market_data_config_from_environment())
    if not enabled_provider_configs(config):
        raise RuntimeError("no enabled live market data provider")
    engine = create_postgres_engine(Settings().database_url)
    collector = ForwardOutcomeCollector(
        PostgresPortfolioLifecycleRepository(engine),
        PostgresForwardOutcomeRepository(engine),
        MarketDataOutcomeEvidenceSource(
            config, transport_factory, PostgresAcquisitionAttemptRepository(engine)
        ),
        enrollments=PostgresProposalEnrollmentRepository(engine),
    )
    summary = collector.collect(now or datetime.now(UTC))
    _LOGGER.info("forward_outcome_collection", extra={"summary": asdict(summary)})
    return summary


def main() -> int:
    run_scheduled_outcome_collection()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
