"""Postgres-backed screening state repository (API-001, SPRINT-008).

Implements the root-level screening.state.ScreeningStateRepository
Protocol -- raw SQL through sqlalchemy.Engine/text(), no ORM, matching this
codebase's existing PostgresRunPublicationRepository pattern exactly.
Stores only the latest evaluated state per (signal_id, symbol): upsert()
always overwrites via ON CONFLICT DO UPDATE, never accumulates historical
rows.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from screening.state import ScreeningStateRecord


class PostgresScreeningStateRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert(self, record: ScreeningStateRecord) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO screening_state (
                        signal_id, symbol, signal_version, outcome, explanation,
                        metrics, updated_at, dependency_timestamps
                    ) VALUES (
                        :signal_id, :symbol, :signal_version, :outcome, :explanation,
                        :metrics, :updated_at, :dependency_timestamps
                    )
                    ON CONFLICT (signal_id, symbol) DO UPDATE SET
                        signal_version = EXCLUDED.signal_version,
                        outcome = EXCLUDED.outcome,
                        explanation = EXCLUDED.explanation,
                        metrics = EXCLUDED.metrics,
                        updated_at = EXCLUDED.updated_at,
                        dependency_timestamps = EXCLUDED.dependency_timestamps
                """),
                _to_row(record),
            )

    def get_all(self) -> tuple[ScreeningStateRecord, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text("SELECT * FROM screening_state ORDER BY signal_id, symbol")
            ).mappings()
            return tuple(_to_record(row) for row in rows)

    def get_for_signal(self, signal_id: str) -> tuple[ScreeningStateRecord, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text("SELECT * FROM screening_state WHERE signal_id = :signal_id ORDER BY symbol"),
                {"signal_id": signal_id},
            ).mappings()
            return tuple(_to_record(row) for row in rows)

    def get_one(self, signal_id: str, symbol: str) -> ScreeningStateRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM screening_state "
                        "WHERE signal_id = :signal_id AND symbol = :symbol"
                    ),
                    {"signal_id": signal_id, "symbol": symbol},
                )
                .mappings()
                .first()
            )
            return None if row is None else _to_record(row)


def _to_row(record: ScreeningStateRecord) -> dict[str, object]:
    # text()-based raw SQL carries no column-type metadata, so psycopg has
    # no adapter for a plain Python dict on write (unlike reads, where it
    # auto-parses a json/jsonb column back into a dict using the server-
    # reported column type) -- explicit json.dumps() here, relying on
    # Postgres's own implicit text-to-json cast for the JSON column.
    return {
        "signal_id": record.signal_id,
        "symbol": record.symbol,
        "signal_version": record.signal_version,
        "outcome": record.outcome,
        "explanation": record.explanation,
        "metrics": json.dumps(record.metrics),
        "updated_at": record.updated_at,
        "dependency_timestamps": json.dumps(
            {key: value.isoformat() for key, value in record.dependency_timestamps.items()}
        ),
    }


def _to_record(row: RowMapping) -> ScreeningStateRecord:
    return ScreeningStateRecord(
        signal_id=row["signal_id"],
        signal_version=row["signal_version"],
        symbol=row["symbol"],
        outcome=row["outcome"],
        explanation=row["explanation"],
        metrics=dict(row["metrics"]),
        updated_at=row["updated_at"],
        dependency_timestamps={
            key: datetime.fromisoformat(value)
            for key, value in row["dependency_timestamps"].items()
        },
    )
