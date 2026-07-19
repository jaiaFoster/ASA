from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection, RowMapping

from asa.domain.runs import (
    PublicationRecord,
    RunRecord,
    RunStatus,
    RunStep,
    RunStepName,
    RunStepStatus,
)


class PostgresRunPublicationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_run(
        self,
        requested_at: datetime,
        release_sha: str,
        effective_config_hash: str,
    ) -> RunRecord:
        run_id = uuid4()
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO runs (
                        id, status, requested_at, release_sha, effective_config_hash
                    ) VALUES (
                        :id, 'requested', :requested_at, :release_sha, :config_hash
                    )
                """),
                {
                    "id": run_id,
                    "requested_at": requested_at,
                    "release_sha": release_sha,
                    "config_hash": effective_config_hash,
                },
            )
            connection.execute(
                text("""
                    INSERT INTO run_steps (run_id, step_name, status)
                    SELECT :run_id, step_name, 'pending'
                    FROM unnest(CAST(:steps AS text[])) AS step_name
                """),
                {"run_id": run_id, "steps": [step.value for step in RunStepName]},
            )
        created = self.get_run(run_id)
        if created is None:
            raise RuntimeError("created run could not be read")
        return created

    def start_run(self, run_id: UUID, started_at: datetime) -> None:
        self._transition_run(run_id, RunStatus.REQUESTED, RunStatus.RUNNING, started_at)

    def start_step(self, run_id: UUID, step: RunStepName, started_at: datetime) -> None:
        self._update_step(run_id, step, RunStepStatus.PENDING, RunStepStatus.RUNNING, started_at)

    def complete_step(self, run_id: UUID, step: RunStepName, completed_at: datetime) -> None:
        self._update_step(
            run_id,
            step,
            RunStepStatus.RUNNING,
            RunStepStatus.SUCCEEDED,
            completed_at,
        )

    def fail_run(
        self,
        run_id: UUID,
        failed_step: RunStepName,
        completed_at: datetime,
        failure_code: str,
        failure_detail: str,
    ) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    UPDATE run_steps
                    SET status = 'failed', completed_at = :completed_at,
                        failure_detail = :failure_detail
                    WHERE run_id = :run_id AND step_name = :step_name
                      AND status IN ('pending', 'running')
                """),
                {
                    "run_id": run_id,
                    "step_name": failed_step.value,
                    "completed_at": completed_at,
                    "failure_detail": failure_detail,
                },
            )
            result = connection.execute(
                text("""
                    UPDATE runs
                    SET status = 'failed', completed_at = :completed_at,
                        failure_code = :failure_code, failure_detail = :failure_detail
                    WHERE id = :run_id AND status IN ('requested', 'running')
                """),
                {
                    "run_id": run_id,
                    "completed_at": completed_at,
                    "failure_code": failure_code,
                    "failure_detail": failure_detail,
                },
            )
            if result.rowcount != 1:
                raise ValueError("run cannot transition to failed")

    def get_run(self, run_id: UUID) -> RunRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM runs WHERE id = :run_id"), {"run_id": run_id}
                )
                .mappings()
                .first()
            )
            return None if row is None else self._to_run(connection, row)

    def latest_run(self) -> RunRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM runs ORDER BY requested_at DESC, id DESC LIMIT 1")
                )
                .mappings()
                .first()
            )
            return None if row is None else self._to_run(connection, row)

    def current_publication(self) -> PublicationRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("""
                    SELECT p.id, p.run_id, p.snapshot_id, p.published_at
                    FROM publication_pointer pp
                    JOIN publications p ON p.id = pp.publication_id
                    WHERE pp.id = 1
                """)
                )
                .mappings()
                .first()
            )
        return None if row is None else self._to_publication(row)

    def publish_snapshot(
        self,
        run_id: UUID,
        observed_at: datetime,
        provider: str,
        provider_request_id: str,
        published_at: datetime,
    ) -> PublicationRecord:
        publication_id, snapshot_id = new_publication_ids()
        with self._engine.begin() as connection:
            self._begin_publish_step(connection, run_id, published_at)
            connection.execute(
                text("""
                    INSERT INTO portfolio_snapshots (
                        id, run_id, observed_at, provider, provider_request_id
                    ) VALUES (
                        :id, :run_id, :observed_at, :provider, :provider_request_id
                    )
                """),
                {
                    "id": snapshot_id,
                    "run_id": run_id,
                    "observed_at": observed_at,
                    "provider": provider,
                    "provider_request_id": provider_request_id,
                },
            )
            run_result = connection.execute(
                text("""
                    UPDATE runs SET status = 'succeeded', completed_at = :published_at
                    WHERE id = :run_id AND status = 'running'
                """),
                {"run_id": run_id, "published_at": published_at},
            )
            if run_result.rowcount != 1:
                raise ValueError("only a running run can publish")
            connection.execute(
                text("""
                    INSERT INTO publications (id, run_id, snapshot_id, published_at)
                    VALUES (:id, :run_id, :snapshot_id, :published_at)
                """),
                {
                    "id": publication_id,
                    "run_id": run_id,
                    "snapshot_id": snapshot_id,
                    "published_at": published_at,
                },
            )
            connection.execute(
                text("""
                    INSERT INTO publication_pointer (id, publication_id)
                    VALUES (1, :publication_id)
                    ON CONFLICT (id) DO UPDATE
                    SET publication_id = EXCLUDED.publication_id
                """),
                {"publication_id": publication_id},
            )
            step_result = connection.execute(
                text("""
                    UPDATE run_steps SET status = 'succeeded', completed_at = :published_at
                    WHERE run_id = :run_id AND step_name = 'publish' AND status = 'running'
                """),
                {"run_id": run_id, "published_at": published_at},
            )
            if step_result.rowcount != 1:
                raise ValueError("publish step was not running")
        return PublicationRecord(
            id=publication_id,
            run_id=run_id,
            snapshot_id=snapshot_id,
            published_at=published_at,
        )

    def _transition_run(
        self,
        run_id: UUID,
        current: RunStatus,
        target: RunStatus,
        changed_at: datetime,
    ) -> None:
        timestamp_column = "started_at" if target is RunStatus.RUNNING else "completed_at"
        with self._engine.begin() as connection:
            result = connection.execute(
                text(f"""
                    UPDATE runs SET status = :target, {timestamp_column} = :changed_at
                    WHERE id = :run_id AND status = :current
                """),
                {
                    "run_id": run_id,
                    "target": target.value,
                    "current": current.value,
                    "changed_at": changed_at,
                },
            )
            if result.rowcount != 1:
                raise ValueError(f"run cannot transition from {current} to {target}")

    def _update_step(
        self,
        run_id: UUID,
        step: RunStepName,
        current: RunStepStatus,
        target: RunStepStatus,
        changed_at: datetime,
    ) -> None:
        timestamp_column = "started_at" if target is RunStepStatus.RUNNING else "completed_at"
        with self._engine.begin() as connection:
            result = connection.execute(
                text(f"""
                    UPDATE run_steps SET status = :target, {timestamp_column} = :changed_at
                    WHERE run_id = :run_id AND step_name = :step AND status = :current
                """),
                {
                    "run_id": run_id,
                    "step": step.value,
                    "target": target.value,
                    "current": current.value,
                    "changed_at": changed_at,
                },
            )
            if result.rowcount != 1:
                raise ValueError(f"step {step} cannot transition from {current} to {target}")

    @staticmethod
    def _begin_publish_step(
        connection: Connection,
        run_id: UUID,
        started_at: datetime,
    ) -> None:
        result = connection.execute(
            text("""
                UPDATE run_steps SET status = 'running', started_at = :started_at
                WHERE run_id = :run_id AND step_name = 'publish' AND status = 'pending'
            """),
            {"run_id": run_id, "started_at": started_at},
        )
        if result.rowcount != 1:
            raise ValueError("publish step cannot start")

    @staticmethod
    def _to_run(connection: Connection, row: RowMapping) -> RunRecord:
        step_rows = connection.execute(
            text("""
                SELECT step_name, status, started_at, completed_at, failure_detail
                FROM run_steps WHERE run_id = :run_id ORDER BY id
            """),
            {"run_id": row["id"]},
        ).mappings()
        return RunRecord(
            id=row["id"],
            status=RunStatus(row["status"]),
            requested_at=row["requested_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            release_sha=row["release_sha"],
            effective_config_hash=row["effective_config_hash"],
            failure_code=row["failure_code"],
            failure_detail=row["failure_detail"],
            steps=tuple(
                RunStep(
                    name=RunStepName(item["step_name"]),
                    status=RunStepStatus(item["status"]),
                    started_at=item["started_at"],
                    completed_at=item["completed_at"],
                    failure_detail=item["failure_detail"],
                )
                for item in step_rows
            ),
        )

    @staticmethod
    def _to_publication(row: RowMapping) -> PublicationRecord:
        return PublicationRecord(
            id=row["id"],
            run_id=row["run_id"],
            snapshot_id=row["snapshot_id"],
            published_at=row["published_at"],
        )


def new_publication_ids() -> tuple[UUID, UUID]:
    return uuid4(), uuid4()
