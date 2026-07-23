import os
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from asa.contracts.runs import RunStatus, RunStepName, RunStepStatus
from asa.integrations.runs_postgres import PostgresRunPublicationRepository


@pytest.fixture
def run_repository() -> PostgresRunPublicationRepository:
    database_url = os.environ["ASA_TEST_DATABASE_URL"]
    os.environ["ASA_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE publication_pointer, publications, portfolio_snapshots, "
                "run_steps, runs CASCADE"
            )
        )
    return PostgresRunPublicationRepository(engine)


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.getenv("ASA_TEST_DATABASE_URL"),
        reason="ASA_TEST_DATABASE_URL not set",
    ),
]


def test_run_steps_and_atomic_publication(run_repository: PostgresRunPublicationRepository) -> None:
    now = datetime.now(UTC)
    run = run_repository.create_run(now, "release-a", "config-a")
    run_repository.start_run(run.id, now)
    for step in (
        RunStepName.ACQUIRE_PORTFOLIO,
        RunStepName.NORMALIZE_PORTFOLIO,
        RunStepName.VALIDATE_PUBLICATION,
    ):
        run_repository.start_step(run.id, step, now)
        run_repository.complete_step(run.id, step, now)
    publication = run_repository.publish_snapshot(
        run.id, now, "deterministic_fake", "broker-request-a", now
    )

    persisted = run_repository.get_run(run.id)
    assert persisted is not None
    assert persisted.status is RunStatus.SUCCEEDED
    assert all(step.status is RunStepStatus.SUCCEEDED for step in persisted.steps)
    assert run_repository.current_publication() == publication


def test_failed_run_preserves_current_publication(
    run_repository: PostgresRunPublicationRepository,
) -> None:
    now = datetime.now(UTC)
    successful = run_repository.create_run(now, "release-a", "config-a")
    run_repository.start_run(successful.id, now)
    for step in (
        RunStepName.ACQUIRE_PORTFOLIO,
        RunStepName.NORMALIZE_PORTFOLIO,
        RunStepName.VALIDATE_PUBLICATION,
    ):
        run_repository.start_step(successful.id, step, now)
        run_repository.complete_step(successful.id, step, now)
    publication = run_repository.publish_snapshot(
        successful.id, now, "deterministic_fake", "broker-request-a", now
    )

    failed = run_repository.create_run(now, "release-b", "config-b")
    run_repository.start_run(failed.id, now)
    run_repository.start_step(failed.id, RunStepName.ACQUIRE_PORTFOLIO, now)
    run_repository.fail_run(
        failed.id,
        RunStepName.ACQUIRE_PORTFOLIO,
        now,
        "provider_failed",
        "sanitized failure",
    )

    assert run_repository.current_publication() == publication
