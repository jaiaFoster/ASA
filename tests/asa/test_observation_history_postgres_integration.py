"""SPRINT-009R/EPIC-R3: strategy_runtime.service.record_opportunity_observation()
and strategy_runtime.persistence.replay_opportunity_history() exercised end
to end against a real (test) Postgres instance, through
PostgresObservationHistoryRepository.

Mirrors tests/asa/test_universal_screening_service_postgres_integration.py's
own exact pattern (EPIC-9) for the same reason: proving append()/
history_for() actually compose correctly through the real raw-SQL layer,
not just that each works in isolation. Uses a fake, generically-named
lifecycle-tracking strategy ("watched_event") rather than the real
earnings_calendar adapter -- proving the persistence layer is genuinely
strategy-agnostic, the same way tests/strategy_runtime/test_lifecycle.py
already does for the in-memory engine.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.integrations.observation_history_postgres import PostgresObservationHistoryRepository
from strategy_runtime import (
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    RowType,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.lifecycle import RecommendedAction, compute_opportunity_id
from strategy_runtime.persistence import replay_opportunity_history
from strategy_runtime.result import EvaluationState
from strategy_runtime.service import record_opportunity_observation

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]

STRATEGY_ID = "watched_event"
SYMBOL = "AAPL"


@pytest.fixture(scope="module", autouse=True)
def _migrated_database() -> None:
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def repository() -> PostgresObservationHistoryRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE opportunity_observation_history"))
    return PostgresObservationHistoryRepository(engine)


def _contract() -> StrategyContract:
    return StrategyContract(
        strategy_id=STRATEGY_ID,
        version="1.0.0",
        category="test",
        description="A fake lifecycle-tracking strategy for EPIC-R3 integration tests.",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        lifecycle=LifecycleDeclaration(
            LifecycleModel.OPPORTUNITY,
            supported_states=("watching", "confirmed"),
            observation_type="watched_event",
        ),
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
    )


def _adapter(context: object) -> UniversalScreeningResult:  # never invoked directly in this test
    raise NotImplementedError


def _result(
    stage: str, verdict: str, run_id: str, observed_at: datetime
) -> UniversalScreeningResult:
    opportunity_id = compute_opportunity_id(STRATEGY_ID, SYMBOL, "event-1")
    return UniversalScreeningResult(
        strategy_id=STRATEGY_ID,
        strategy_version="1.0.0",
        symbol=SYMBOL,
        observation_id=compute_observation_id(run_id, STRATEGY_ID, SYMBOL),
        opportunity_id=opportunity_id,
        row_type=RowType.RESULT,
        verdict=verdict,
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=stage,
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=(),
        warnings=(),
        provenance=(),
        observed_at=observed_at,
    )


def test_recorded_observations_replay_in_order_through_real_postgres(
    repository: PostgresObservationHistoryRepository,
) -> None:
    registry = StrategyRegistry(((_contract(), _adapter),))
    start = datetime(2026, 7, 23, 16, 0, tzinfo=UTC)

    watching = record_opportunity_observation(
        registry,
        repository,
        _result("watching", "monitoring", "run-1", start),
        recommended_action=RecommendedAction.MONITOR,
    )
    confirmed = record_opportunity_observation(
        registry,
        repository,
        _result("confirmed", "confirmed", "run-2", start + timedelta(days=1)),
        recommended_action=RecommendedAction.ENTER,
    )

    history = replay_opportunity_history(repository, watching.opportunity_id)

    assert history is not None
    assert history.observations == (watching, confirmed)
    assert history.current == confirmed


def test_replay_of_an_unknown_opportunity_returns_none(
    repository: PostgresObservationHistoryRepository,
) -> None:
    assert replay_opportunity_history(repository, "no-such-opportunity") is None
