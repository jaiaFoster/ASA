"""Postgres-backed LatestResultRepository (SPRINT-009/EPIC-9).

Implements strategy_runtime.persistence.LatestResultRepository -- raw SQL
through sqlalchemy.Engine/text(), no ORM. Stores only
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
from datetime import date, datetime

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from strategy_runtime.persistence import UniversalSignalRow
from strategy_runtime.result import ResultTemporalMetadata
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
                        metrics, economics, blockers, warnings, provenance, observed_at,
                        temporal
                    ) VALUES (
                        :signal_id, :symbol, :signal_version, :observation_id,
                        :opportunity_id, :row_type, :verdict, :evaluation_state,
                        :lifecycle_stage, :recommendation_state, :data_quality,
                        :metrics, :economics, :blockers, :warnings, :provenance, :observed_at,
                        :temporal
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
                        observed_at = EXCLUDED.observed_at,
                        temporal = EXCLUDED.temporal
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
        "temporal": (
            None
            if row.temporal is None
            else json.dumps(
                {
                    "observed_at": row.temporal.observed_at.isoformat(),
                    "received_at": row.temporal.received_at.isoformat(),
                    "evaluated_at": row.temporal.evaluated_at.isoformat(),
                    "persisted_at": row.temporal.persisted_at.isoformat(),
                    "market_session_date": row.temporal.market_session_date.isoformat(),
                    "market_session_status": row.temporal.market_session_status,
                    "age_seconds": row.temporal.age_seconds,
                    "last_refresh_attempt_at": row.temporal.last_refresh_attempt_at.isoformat(),
                    "last_successful_refresh_at": (
                        row.temporal.last_successful_refresh_at.isoformat()
                    ),
                    "next_refresh_at": (
                        None
                        if row.temporal.next_refresh_at is None
                        else row.temporal.next_refresh_at.isoformat()
                    ),
                    "data_advanced_on_last_refresh": (
                        row.temporal.data_advanced_on_last_refresh
                    ),
                    "freshness_status": row.temporal.freshness_status,
                    "usability_status": row.temporal.usability_status,
                    "usability_reason": row.temporal.usability_reason,
                    "warning_codes": list(row.temporal.warning_codes),
                    "acquisition_started_at": (
                        row.temporal.acquisition_started_at.isoformat()
                    ),
                    "acquisition_completed_at": (
                        row.temporal.acquisition_completed_at.isoformat()
                    ),
                    "input_time_skew_seconds": row.temporal.input_time_skew_seconds,
                }
            )
        ),
    }


def _to_row(mapping: RowMapping) -> UniversalSignalRow:
    temporal_data = mapping.get("temporal")
    temporal = (
        None
        if temporal_data is None
        else ResultTemporalMetadata(
            observed_at=datetime.fromisoformat(temporal_data["observed_at"]),
            received_at=datetime.fromisoformat(temporal_data["received_at"]),
            evaluated_at=datetime.fromisoformat(temporal_data["evaluated_at"]),
            persisted_at=datetime.fromisoformat(temporal_data["persisted_at"]),
            market_session_date=date.fromisoformat(temporal_data["market_session_date"]),
            market_session_status=temporal_data["market_session_status"],
            age_seconds=temporal_data["age_seconds"],
            last_refresh_attempt_at=datetime.fromisoformat(
                temporal_data["last_refresh_attempt_at"]
            ),
            last_successful_refresh_at=datetime.fromisoformat(
                temporal_data["last_successful_refresh_at"]
            ),
            next_refresh_at=(
                None
                if temporal_data["next_refresh_at"] is None
                else datetime.fromisoformat(temporal_data["next_refresh_at"])
            ),
            data_advanced_on_last_refresh=temporal_data[
                "data_advanced_on_last_refresh"
            ],
            freshness_status=temporal_data["freshness_status"],
            usability_status=temporal_data["usability_status"],
            usability_reason=temporal_data["usability_reason"],
            warning_codes=tuple(temporal_data["warning_codes"]),
            acquisition_started_at=datetime.fromisoformat(
                temporal_data["acquisition_started_at"]
            ),
            acquisition_completed_at=datetime.fromisoformat(
                temporal_data["acquisition_completed_at"]
            ),
            input_time_skew_seconds=temporal_data["input_time_skew_seconds"],
        )
    )
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
        temporal=temporal,
    )
