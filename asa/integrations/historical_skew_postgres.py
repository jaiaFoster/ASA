"""Postgres-backed HistoricalSkewRepository (SPRINT-013 S13-04B).

Implements strategy_runtime.historical_evidence.HistoricalSkewRepository --
raw SQL through sqlalchemy.Engine/text(), no ORM, matching this codebase's
established PostgresLatestResultRepository/PostgresObservationHistoryRepository
pattern exactly.

Uniqueness is enforced in PostgreSQL itself (migrations/versions/0012_
historical_skew_observations.py's own primary key on (instrument_scheme,
instrument_value, trading_session_date)), not only in application code --
append() uses INSERT ... ON CONFLICT DO NOTHING RETURNING, then, only when
nothing was returned (a row for this session already existed), reads that
row back and compares financial values. This is race-safe under real
concurrent writers: the database's own primary key resolves which of two
truly simultaneous inserts for the same (instrument, session) actually
wins atomically; both callers then agree, from the row Postgres now
durably holds, whether their own attempt was a same-values idempotent
no-op or a genuine content conflict. No naive "check then insert" -- that
shape has a race window this one does not.

HISTORICAL_SKEW_SCHEMA_VERSION is stamped on every row this repository
writes. It is not part of HistoricalSkewRepository's own Protocol, and
domain.strategy_evidence.HistoricalSkewObservation itself is deliberately
unchanged (see project/reports/SPRINT-013-S13-04-trace.md and PR #274's
own scope note) -- this is pure persistence-layer bookkeeping, giving a
future normalization revision a traceable boundary without ever having to
guess, or silently reinterpret, what an already-recorded row originally
meant.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from domain import CanonicalInstrumentIdentity, EvidenceKind, EvidenceReference
from domain.strategy_evidence import HistoricalSkewObservation
from strategy_runtime.historical_evidence import ConflictingHistoricalObservationError

HISTORICAL_SKEW_SCHEMA_VERSION = "1.0.0"


class PostgresHistoricalSkewRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(self, observation: HistoricalSkewObservation, *, session_date: date) -> None:
        with self._engine.begin() as connection:
            inserted = connection.execute(
                text("""
                    INSERT INTO historical_skew_observations (
                        instrument_scheme, instrument_value, trading_session_date,
                        call_skew, put_skew, effective_time, evidence, schema_version
                    ) VALUES (
                        :instrument_scheme, :instrument_value, :trading_session_date,
                        :call_skew, :put_skew, :effective_time, :evidence, :schema_version
                    )
                    ON CONFLICT (instrument_scheme, instrument_value, trading_session_date)
                    DO NOTHING
                    RETURNING instrument_scheme
                """),
                _insert_params(observation, session_date),
            ).first()
            if inserted is not None:
                return
            existing = connection.execute(
                text("""
                    SELECT call_skew, put_skew FROM historical_skew_observations
                    WHERE instrument_scheme = :instrument_scheme
                      AND instrument_value = :instrument_value
                      AND trading_session_date = :trading_session_date
                """),
                {
                    "instrument_scheme": observation.instrument.scheme,
                    "instrument_value": observation.instrument.value,
                    "trading_session_date": session_date,
                },
            ).one()
            if (existing.call_skew, existing.put_skew) != (
                observation.call_skew,
                observation.put_skew,
            ):
                raise ConflictingHistoricalObservationError(
                    f"{observation.instrument} already has a recorded observation "
                    f"for session {session_date} with different skew values"
                )

    def history_for(
        self,
        instrument: CanonicalInstrumentIdentity,
        *,
        as_of: datetime | None = None,
        maximum_observations: int | None = None,
    ) -> tuple[HistoricalSkewObservation, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text("""
                    SELECT * FROM (
                        SELECT * FROM historical_skew_observations
                        WHERE instrument_scheme = :instrument_scheme
                          AND instrument_value = :instrument_value
                          AND (
                              CAST(:as_of AS TIMESTAMP WITH TIME ZONE) IS NULL
                              OR effective_time <= :as_of
                          )
                        ORDER BY trading_session_date DESC
                        LIMIT :maximum_observations
                    ) AS latest
                    ORDER BY trading_session_date ASC
                """),
                {
                    "instrument_scheme": instrument.scheme,
                    "instrument_value": instrument.value,
                    "as_of": as_of,
                    "maximum_observations": maximum_observations,
                },
            ).mappings()
            return tuple(_to_observation(row) for row in rows)


def _insert_params(observation: HistoricalSkewObservation, session_date: date) -> dict[str, object]:
    return {
        "instrument_scheme": observation.instrument.scheme,
        "instrument_value": observation.instrument.value,
        "trading_session_date": session_date,
        "call_skew": observation.call_skew,
        "put_skew": observation.put_skew,
        "effective_time": observation.effective_time,
        "evidence": json.dumps([_evidence_to_json(item) for item in observation.evidence]),
        "schema_version": HISTORICAL_SKEW_SCHEMA_VERSION,
    }


def _evidence_to_json(item: EvidenceReference) -> dict[str, object]:
    return {"kind": item.kind.value, "referenced_id": item.referenced_id, "version": item.version}


def _evidence_from_json(payload: list[dict[str, object]]) -> tuple[EvidenceReference, ...]:
    references: list[EvidenceReference] = []
    for item in payload:
        version = item["version"]
        assert version is None or isinstance(version, int)
        references.append(
            EvidenceReference(EvidenceKind(item["kind"]), str(item["referenced_id"]), version)
        )
    return tuple(references)


def _to_observation(row: RowMapping) -> HistoricalSkewObservation:
    return HistoricalSkewObservation(
        instrument=CanonicalInstrumentIdentity(row["instrument_scheme"], row["instrument_value"]),
        call_skew=row["call_skew"],
        put_skew=row["put_skew"],
        effective_time=row["effective_time"],
        evidence=_evidence_from_json(row["evidence"]),
    )
