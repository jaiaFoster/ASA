"""Postgres-backed LatestResultRepository (SPRINT-009/EPIC-9).

Implements strategy_runtime.persistence.LatestResultRepository -- raw SQL
through sqlalchemy.Engine/text(), no ORM, matching this codebase's
existing PostgresScreeningStateRepository pattern exactly. Stores only
the latest UniversalSignalRow per (signal_id, symbol): upsert()
always overwrites via ON CONFLICT DO UPDATE, never accumulates historical
rows -- observation history (strategy_runtime.persistence.
ObservationHistoryRepository) is a separate concern, not this
repository's job, and its own concrete implementation remains deferred
(strategy_runtime/persistence.py's own documented scope decision).

Works exclusively with UniversalSignalRow, never UniversalScreeningResult
directly: tests/asa/test_boundaries.py::
test_forbidden_legacy_technologies_are_absent bans the literal substring
"strategy" anywhere under asa/, and UniversalSignalRow is the
already-renamed (signal_id/signal_version) projection that lets this
module satisfy that rule -- see strategy_runtime/persistence.py's own
docstring for the full rationale.
"""

from __future__ import annotations

import json

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.values import TypedValue


class PostgresLatestResultRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert(self, row: UniversalSignalRow) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO universal_screening_state (
                        signal_id, symbol, signal_version, observation_id,
                        opportunity_id, row_type, verdict, evaluation_state,
                        lifecycle_stage, recommendation_state, data_quality,
                        metrics, economics, blockers, warnings, provenance, observed_at
                    ) VALUES (
                        :signal_id, :symbol, :signal_version, :observation_id,
                        :opportunity_id, :row_type, :verdict, :evaluation_state,
                        :lifecycle_stage, :recommendation_state, :data_quality,
                        :metrics, :economics, :blockers, :warnings, :provenance, :observed_at
                    )
                    ON CONFLICT (signal_id, symbol) DO UPDATE SET
                        signal_version = EXCLUDED.signal_version,
                        observation_id = EXCLUDED.observation_id,
                        opportunity_id = EXCLUDED.opportunity_id,
                        row_type = EXCLUDED.row_type,
                        verdict = EXCLUDED.verdict,
                        evaluation_state = EXCLUDED.evaluation_state,
                        lifecycle_stage = EXCLUDED.lifecycle_stage,
                        recommendation_state = EXCLUDED.recommendation_state,
                        data_quality = EXCLUDED.data_quality,
                        metrics = EXCLUDED.metrics,
                        economics = EXCLUDED.economics,
                        blockers = EXCLUDED.blockers,
                        warnings = EXCLUDED.warnings,
                        provenance = EXCLUDED.provenance,
                        observed_at = EXCLUDED.observed_at
                """),
                _to_params(row),
            )

    def get_all(self) -> tuple[UniversalSignalRow, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text("SELECT * FROM universal_screening_state ORDER BY signal_id, symbol")
            ).mappings()
            return tuple(_to_row(row) for row in rows)

    def get_for_signal(self, signal_id: str) -> tuple[UniversalSignalRow, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT * FROM universal_screening_state "
                    "WHERE signal_id = :signal_id ORDER BY symbol"
                ),
                {"signal_id": signal_id},
            ).mappings()
            return tuple(_to_row(row) for row in rows)

    def get_one(self, signal_id: str, symbol: str) -> UniversalSignalRow | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM universal_screening_state "
                        "WHERE signal_id = :signal_id AND symbol = :symbol"
                    ),
                    {"signal_id": signal_id, "symbol": symbol},
                )
                .mappings()
                .first()
            )
            return None if row is None else _to_row(row)


def _to_params(row: UniversalSignalRow) -> dict[str, object]:
    # text()-based raw SQL carries no column-type metadata, so psycopg has
    # no adapter for a plain Python list/dict on write (unlike reads,
    # where it auto-parses a json/jsonb column back using the server-
    # reported column type) -- explicit json.dumps() here, relying on
    # Postgres's own implicit text-to-json cast for the JSON columns.
    return {
        "signal_id": row.signal_id,
        "symbol": row.symbol,
        "signal_version": row.signal_version,
        "observation_id": row.observation_id,
        "opportunity_id": row.opportunity_id,
        "row_type": row.row_type,
        "verdict": row.verdict,
        "evaluation_state": row.evaluation_state,
        "lifecycle_stage": row.lifecycle_stage,
        "recommendation_state": row.recommendation_state,
        "data_quality": row.data_quality,
        "metrics": json.dumps({key: value.to_json() for key, value in row.metrics.items()}),
        "economics": json.dumps({key: value.to_json() for key, value in row.economics.items()}),
        "blockers": json.dumps(list(row.blockers)),
        "warnings": json.dumps(list(row.warnings)),
        "provenance": json.dumps(list(row.provenance)),
        "observed_at": row.observed_at,
    }


def _to_row(mapping: RowMapping) -> UniversalSignalRow:
    return UniversalSignalRow(
        signal_id=mapping["signal_id"],
        signal_version=mapping["signal_version"],
        symbol=mapping["symbol"],
        observation_id=mapping["observation_id"],
        opportunity_id=mapping["opportunity_id"],
        row_type=mapping["row_type"],
        verdict=mapping["verdict"],
        evaluation_state=mapping["evaluation_state"],
        lifecycle_stage=mapping["lifecycle_stage"],
        recommendation_state=mapping["recommendation_state"],
        data_quality=mapping["data_quality"],
        metrics={key: TypedValue.from_json(value) for key, value in mapping["metrics"].items()},
        economics={
            key: TypedValue.from_json(value) for key, value in mapping["economics"].items()
        },
        blockers=tuple(mapping["blockers"]),
        warnings=tuple(mapping["warnings"]),
        provenance=tuple(mapping["provenance"]),
        observed_at=mapping["observed_at"],
    )
