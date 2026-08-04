"""PostgreSQL-backed AcquisitionAttemptRepository (SPRINT-013 S13-02).

Raw SQL through sqlalchemy.Engine/text(), no ORM -- matches every other
asa/integrations repository. Idempotent on (pair_evaluation_id, sequence)
via ON CONFLICT DO NOTHING, the same pattern
asa.integrations.refresh_schedule_postgres.PostgresRefreshScheduleClaimRepository
already uses for its own idempotency key, so record() re-recording the
exact same attempt is a silent no-op, never a duplicate row and never an
error -- matching InMemoryAcquisitionAttemptRepository's semantics exactly
(market_data.attempts.AcquisitionAttemptRepository's own documented
contract).
"""

from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from domain import MarketCapability
from market_data.attempts import (
    AcquisitionAttemptRecord,
    AcquisitionOutcome,
    AttemptQuery,
)
from market_data.fulfillment import FulfillmentStatus
from market_data.providers import ProviderErrorCode


class PostgresAcquisitionAttemptRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record(self, attempts: tuple[AcquisitionAttemptRecord, ...]) -> None:
        if not attempts:
            return
        with self._engine.begin() as connection:
            for attempt in attempts:
                connection.execute(
                    text("""
                        INSERT INTO screening_acquisition_attempts (
                            screening_cycle_id, pair_evaluation_id, sequence, capability,
                            provider_id, priority, fulfillment_status, outcome,
                            diagnostic_code, retryable, safe_summary, recorded_at
                        ) VALUES (
                            :screening_cycle_id, :pair_evaluation_id, :sequence, :capability,
                            :provider_id, :priority, :fulfillment_status, :outcome,
                            :diagnostic_code, :retryable, :safe_summary, :recorded_at
                        )
                        ON CONFLICT (pair_evaluation_id, sequence) DO NOTHING
                    """),
                    _to_params(attempt),
                )

    def query(self, query: AttemptQuery) -> tuple[AcquisitionAttemptRecord, ...]:
        where, params = _where_clause(query)
        params["limit"] = query.limit
        params["offset"] = query.offset
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT * FROM screening_acquisition_attempts "
                    f"{where} "
                    "ORDER BY recorded_at, pair_evaluation_id, sequence "
                    "LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings()
            return tuple(_to_record(row) for row in rows)

    def summarize(self, query: AttemptQuery) -> dict[AcquisitionOutcome, int]:
        where, params = _where_clause(query)
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT outcome, COUNT(*) AS attempt_count "
                    "FROM screening_acquisition_attempts "
                    f"{where} "
                    "GROUP BY outcome"
                ),
                params,
            ).mappings()
            return {AcquisitionOutcome(row["outcome"]): row["attempt_count"] for row in rows}


def _where_clause(query: AttemptQuery) -> tuple[str, dict[str, object]]:
    clauses = []
    params: dict[str, object] = {}
    if query.screening_cycle_id is not None:
        clauses.append("screening_cycle_id = :screening_cycle_id")
        params["screening_cycle_id"] = query.screening_cycle_id
    if query.pair_evaluation_id is not None:
        clauses.append("pair_evaluation_id = :pair_evaluation_id")
        params["pair_evaluation_id"] = query.pair_evaluation_id
    if query.provider_id is not None:
        clauses.append("provider_id = :provider_id")
        params["provider_id"] = query.provider_id
    if query.capability is not None:
        clauses.append("capability = :capability")
        params["capability"] = query.capability.value
    if query.outcome is not None:
        clauses.append("outcome = :outcome")
        params["outcome"] = query.outcome.value
    if query.recorded_after is not None:
        clauses.append("recorded_at >= :recorded_after")
        params["recorded_after"] = query.recorded_after
    if query.recorded_before is not None:
        clauses.append("recorded_at <= :recorded_before")
        params["recorded_before"] = query.recorded_before
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def _to_params(attempt: AcquisitionAttemptRecord) -> dict[str, object]:
    diagnostic_code = None if attempt.diagnostic_code is None else attempt.diagnostic_code.value
    return {
        "screening_cycle_id": attempt.screening_cycle_id,
        "pair_evaluation_id": attempt.pair_evaluation_id,
        "sequence": attempt.sequence,
        "capability": attempt.capability.value,
        "provider_id": attempt.provider_id,
        "priority": attempt.priority,
        "fulfillment_status": attempt.fulfillment_status.value,
        "outcome": attempt.outcome.value,
        "diagnostic_code": diagnostic_code,
        "retryable": attempt.retryable,
        "safe_summary": attempt.safe_summary,
        "recorded_at": attempt.recorded_at,
    }


def _to_record(mapping: RowMapping) -> AcquisitionAttemptRecord:
    return AcquisitionAttemptRecord(
        screening_cycle_id=mapping["screening_cycle_id"],
        pair_evaluation_id=mapping["pair_evaluation_id"],
        sequence=mapping["sequence"],
        capability=MarketCapability(mapping["capability"]),
        provider_id=mapping["provider_id"],
        priority=mapping["priority"],
        fulfillment_status=FulfillmentStatus(mapping["fulfillment_status"]),
        outcome=AcquisitionOutcome(mapping["outcome"]),
        diagnostic_code=(
            None
            if mapping["diagnostic_code"] is None
            else ProviderErrorCode(mapping["diagnostic_code"])
        ),
        retryable=mapping["retryable"],
        safe_summary=mapping["safe_summary"],
        recorded_at=mapping["recorded_at"],
    )
