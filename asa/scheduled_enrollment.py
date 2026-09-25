"""Run-and-exit system proposal enrollment (ND-01).

Invoked from ``asa.scheduled_screening.main`` after the pair loop, in its own
isolated ``try`` and before forward-outcome collection. It reads only this
tick's authoritative latest rows and the readiness artifacts projected from
them; the collector itself never reads latest state.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime

from asa.application.proposal_enrollment import EnrollmentSummary, ProposalEnrollmentService
from asa.config import Settings
from asa.integrations.portfolio_lifecycle_postgres import PostgresPortfolioLifecycleRepository
from asa.integrations.postgres import create_postgres_engine
from asa.integrations.proposal_enrollment_postgres import PostgresProposalEnrollmentRepository
from asa.integrations.universal_screening_postgres import PostgresLatestResultRepository

_LOGGER = logging.getLogger(__name__)


def run_scheduled_proposal_enrollment(
    pairs: Iterable[tuple[str, str, str]], *, now: datetime | None = None
) -> EnrollmentSummary:
    engine = create_postgres_engine(Settings().database_url)
    summary = ProposalEnrollmentService(
        PostgresLatestResultRepository(engine),
        PostgresPortfolioLifecycleRepository(engine),
        PostgresProposalEnrollmentRepository(engine),
    ).enroll(pairs, now or datetime.now(UTC))
    _LOGGER.info("proposal_outcome_enrollment", extra={"summary": asdict(summary)})
    return summary
