"""PostgreSQL-backed idempotency claims for external scheduler delivery."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Engine, text


@dataclass(frozen=True, slots=True)
class ScreeningOperationalHealth:
    last_attempted_batch_at: datetime | None
    last_successful_batch_at: datetime | None
    oldest_subject_age_seconds: int | None
    overdue_subject_count: int
    last_batch_subject_count: int
    last_batch_pair_count: int
    last_batch_failure_count: int
    last_batch_incomplete_diagnostic_count: int


class PostgresRefreshScheduleClaimRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def claim(self, slot_id: str, claimed_at: datetime) -> bool:
        with self._engine.begin() as connection:
            result = connection.execute(
                text("""
                    INSERT INTO refresh_schedule_claims (slot_id, claimed_at)
                    VALUES (:slot_id, :claimed_at)
                    ON CONFLICT (slot_id) DO NOTHING
                    RETURNING slot_id
                """),
                {"slot_id": slot_id, "claimed_at": claimed_at},
            )
            return result.first() is not None


class PostgresSubjectRefreshRepository:
    """Atomic oldest-first subject claims shared by separate cron processes."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def claim_oldest(
        self,
        subject_ids: Sequence[str],
        *,
        claimed_at: datetime,
        maximum_subjects: int,
        lease: timedelta,
    ) -> tuple[str, ...]:
        if maximum_subjects < 1:
            raise ValueError("maximum_subjects must be positive")
        normalized = tuple(sorted(set(subject_ids)))
        if not normalized:
            return ()
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO screening_subject_refresh_state (subject_id)
                    SELECT unnest(CAST(:subject_ids AS text[]))
                    ON CONFLICT (subject_id) DO NOTHING
                """),
                {"subject_ids": list(normalized)},
            )
            rows = connection.execute(
                text("""
                    WITH eligible AS (
                        SELECT subject_id
                        FROM screening_subject_refresh_state
                        WHERE subject_id = ANY(CAST(:subject_ids AS text[]))
                          AND (eligible_after IS NULL OR eligible_after <= :claimed_at)
                          AND (claim_expires_at IS NULL OR claim_expires_at <= :claimed_at)
                        ORDER BY last_completed_at ASC NULLS FIRST, subject_id ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT :maximum_subjects
                    )
                    UPDATE screening_subject_refresh_state AS state
                    SET claimed_at = :claimed_at,
                        claim_expires_at = :claim_expires_at
                    FROM eligible
                    WHERE state.subject_id = eligible.subject_id
                    RETURNING state.subject_id
                """),
                {
                    "subject_ids": list(normalized),
                    "claimed_at": claimed_at,
                    "claim_expires_at": claimed_at + lease,
                    "maximum_subjects": maximum_subjects,
                },
            ).scalars()
            return tuple(sorted(rows))

    def complete(self, subject_id: str, *, completed_at: datetime, succeeded: bool) -> None:
        with self._engine.begin() as connection:
            if succeeded:
                connection.execute(
                    text("""
                        UPDATE screening_subject_refresh_state
                        SET last_completed_at = :completed_at,
                            claimed_at = NULL,
                            claim_expires_at = NULL,
                            eligible_after = NULL,
                            consecutive_failures = 0
                        WHERE subject_id = :subject_id
                    """),
                    {"subject_id": subject_id, "completed_at": completed_at},
                )
                return
            connection.execute(
                text("""
                    UPDATE screening_subject_refresh_state
                    SET claimed_at = NULL,
                        claim_expires_at = NULL,
                        consecutive_failures = consecutive_failures + 1,
                        eligible_after = :completed_at + (
                            CASE
                                WHEN consecutive_failures = 0 THEN INTERVAL '5 minutes'
                                WHEN consecutive_failures = 1 THEN INTERVAL '15 minutes'
                                ELSE INTERVAL '30 minutes'
                            END
                        )
                    WHERE subject_id = :subject_id
                """),
                {"subject_id": subject_id, "completed_at": completed_at},
            )

    def batch_started(self, *, attempted_at: datetime, subject_count: int) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    UPDATE screening_operational_state
                    SET last_attempted_batch_at = :attempted_at,
                        last_batch_subject_count = :subject_count,
                        last_batch_pair_count = 0,
                        last_batch_failure_count = 0,
                        last_batch_incomplete_diagnostic_count = 0
                    WHERE singleton_id = 1
                """),
                {"attempted_at": attempted_at, "subject_count": subject_count},
            )

    def batch_completed(
        self,
        *,
        completed_at: datetime,
        pair_count: int,
        failure_count: int,
        incomplete_diagnostic_count: int,
    ) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    UPDATE screening_operational_state
                    SET last_successful_batch_at = CASE
                            WHEN :failure_count = 0 AND :incomplete_count = 0
                                THEN :completed_at
                            ELSE last_successful_batch_at
                        END,
                        last_batch_pair_count = :pair_count,
                        last_batch_failure_count = :failure_count,
                        last_batch_incomplete_diagnostic_count = :incomplete_count
                    WHERE singleton_id = 1
                """),
                {
                    "completed_at": completed_at,
                    "pair_count": pair_count,
                    "failure_count": failure_count,
                    "incomplete_count": incomplete_diagnostic_count,
                },
            )

    def operational_health(self, *, as_of: datetime) -> ScreeningOperationalHealth:
        with self._engine.connect() as connection:
            row = connection.execute(
                text("""
                    SELECT
                        operational.last_attempted_batch_at,
                        operational.last_successful_batch_at,
                        CASE
                            WHEN COUNT(subject.subject_id) FILTER (
                                WHERE subject.last_completed_at IS NULL
                            ) > 0 THEN NULL
                            ELSE GREATEST(
                                0,
                                EXTRACT(EPOCH FROM (
                                    :as_of - MIN(subject.last_completed_at)
                                ))::bigint
                            )
                        END AS oldest_subject_age_seconds,
                        COUNT(subject.subject_id) FILTER (
                            WHERE subject.last_completed_at IS NULL
                               OR operational.last_successful_batch_at IS NULL
                               OR subject.last_completed_at < operational.last_successful_batch_at
                        ) AS overdue_subject_count,
                        operational.last_batch_subject_count,
                        operational.last_batch_pair_count,
                        operational.last_batch_failure_count,
                        operational.last_batch_incomplete_diagnostic_count
                    FROM screening_operational_state AS operational
                    LEFT JOIN screening_subject_refresh_state AS subject ON TRUE
                    WHERE operational.singleton_id = 1
                    GROUP BY operational.singleton_id
                """),
                {"as_of": as_of},
            ).mappings().one()
        return ScreeningOperationalHealth(
            last_attempted_batch_at=row["last_attempted_batch_at"],
            last_successful_batch_at=row["last_successful_batch_at"],
            oldest_subject_age_seconds=row["oldest_subject_age_seconds"],
            overdue_subject_count=row["overdue_subject_count"],
            last_batch_subject_count=row["last_batch_subject_count"],
            last_batch_pair_count=row["last_batch_pair_count"],
            last_batch_failure_count=row["last_batch_failure_count"],
            last_batch_incomplete_diagnostic_count=row[
                "last_batch_incomplete_diagnostic_count"
            ],
        )
