"""PostgreSQL-backed idempotency claims for external scheduler delivery."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import Engine, text


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
