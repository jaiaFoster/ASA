"""PostgreSQL-backed idempotency claims for external scheduler delivery."""

from __future__ import annotations

from datetime import datetime

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
