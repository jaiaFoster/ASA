"""Insert-only Postgres store for system proposal enrollments (ND-01)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from asa.contracts.forward_outcome import ForwardOutcomeObservation
from asa.contracts.proposal_enrollment import ProposalEnrollment
from asa.integrations.forward_outcome_postgres import AppendOnlyOutcomeLedger

_COLUMNS = (
    "id, enrollment_policy_version, originating_observation_id, opportunity_id, "
    "signal_id, signal_version, symbol, session_date, evidence_observed_at, enrolled_at, "
    "resolved_proposal_identity, resolved_proposal_json"
)


class PostgresProposalEnrollmentRepository:
    """No update or delete path exists by design."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._outcomes = AppendOnlyOutcomeLedger(
            engine, "enrolled_proposal_outcome_observations", "enrollment_id"
        )

    def add(self, enrollment: ProposalEnrollment) -> bool:
        params = {name.strip(): getattr(enrollment, name.strip()) for name in _COLUMNS.split(",")}
        with self._engine.begin() as connection:
            result = connection.execute(
                text(
                    f"INSERT INTO proposal_outcome_enrollments ({_COLUMNS}) VALUES ("
                    + ", ".join(f":{name.strip()}" for name in _COLUMNS.split(","))
                    + ") ON CONFLICT DO NOTHING"
                ),
                params,
            )
        return bool(result.rowcount)

    def count_for_session(self, session_date: date) -> int:
        with self._engine.connect() as connection:
            return int(
                connection.execute(
                    text(
                        "SELECT count(*) FROM proposal_outcome_enrollments "
                        "WHERE session_date = :session_date"
                    ),
                    {"session_date": session_date},
                ).scalar_one()
            )

    def slot_taken(
        self, signal_id: str, signal_version: str, symbol: str, session_date: date
    ) -> bool:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    text(
                        "SELECT 1 FROM proposal_outcome_enrollments WHERE signal_id = :signal_id "
                        "AND signal_version = :signal_version AND symbol = :symbol "
                        "AND session_date = :session_date"
                    ),
                    {
                        "signal_id": signal_id,
                        "signal_version": signal_version,
                        "symbol": symbol,
                        "session_date": session_date,
                    },
                ).first()
                is not None
            )

    def enrollments(self) -> tuple[ProposalEnrollment, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(f"SELECT {_COLUMNS} FROM proposal_outcome_enrollments ORDER BY id")
            ).mappings()
            return tuple(_from_row(row) for row in rows)

    def enrollment(self, enrollment_id: UUID) -> ProposalEnrollment | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(f"SELECT {_COLUMNS} FROM proposal_outcome_enrollments WHERE id = :id"),
                    {"id": enrollment_id},
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else _from_row(row)

    def append_outcome(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        return self._outcomes.append(observation)

    def outcomes_for(self, enrollment_id: UUID) -> tuple[ForwardOutcomeObservation, ...]:
        return self._outcomes.for_subject(enrollment_id)


def _from_row(row: Any) -> ProposalEnrollment:
    return ProposalEnrollment(
        id=UUID(str(row["id"])),
        enrollment_policy_version=row["enrollment_policy_version"],
        originating_observation_id=row["originating_observation_id"],
        opportunity_id=row["opportunity_id"],
        signal_id=row["signal_id"],
        signal_version=row["signal_version"],
        symbol=row["symbol"],
        session_date=row["session_date"],
        evidence_observed_at=row["evidence_observed_at"],
        enrolled_at=row["enrolled_at"],
        resolved_proposal_identity=row["resolved_proposal_identity"],
        resolved_proposal_json=row["resolved_proposal_json"],
    )
