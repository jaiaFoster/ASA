"""Append-only Postgres ledger for forward outcomes (OUTCOME-INTELLIGENCE OI-04)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from asa.application.ports.forward_outcomes import ForwardOutcomeConflictError
from asa.contracts.forward_outcome import ForwardOutcomeObservation
from strategy_runtime.forward_outcome import OutcomeStatus

_VALUE_COLUMNS = (
    "horizon_id, status, due_at, collected_at, "
    "horizon_policy_version, frozen_proposal_identity, observed_at, underlying_price, "
    "modeled_mark, modeled_pnl, mark_basis, mark_model_version, unknown_reasons_json, "
    "provenance_json, content_identity"
)


class AppendOnlyOutcomeLedger:
    """Shared append-only mechanics for one outcome table keyed by a subject column.

    It has no update or delete path by design. It serves ``user_tracked``
    (``forward_outcome_observations``) and, under ND-01, ``system_actionable``
    (``enrolled_proposal_outcome_observations``), with identical semantics.
    """

    def __init__(self, engine: Engine, table: str, key_column: str) -> None:
        self._engine = engine
        self._table = table
        self._key = key_column
        self._columns = f"{key_column}, {_VALUE_COLUMNS}"

    def append(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        params = {
            self._key: observation.subject_id,
            "horizon_id": observation.horizon_id,
            "status": observation.status.value,
            "due_at": observation.due_at,
            "collected_at": observation.collected_at,
            "horizon_policy_version": observation.horizon_policy_version,
            "frozen_proposal_identity": observation.frozen_proposal_identity,
            "observed_at": observation.observed_at,
            "underlying_price": observation.underlying_price,
            "modeled_mark": observation.modeled_mark,
            "modeled_pnl": observation.modeled_pnl,
            "mark_basis": observation.mark_basis,
            "mark_model_version": observation.mark_model_version,
            "unknown_reasons_json": json.dumps(list(observation.unknown_reasons)),
            "provenance_json": json.dumps(list(observation.provenance)),
            "content_identity": observation.content_identity,
        }
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    f"INSERT INTO {self._table} ({self._columns}) VALUES ("
                    + ", ".join(f":{name.strip()}" for name in self._columns.split(","))
                    + f") ON CONFLICT ({self._key}, horizon_id) DO NOTHING"
                ),
                params,
            )
            row = (
                connection.execute(
                    text(
                        f"SELECT {self._columns} FROM {self._table} "
                        f"WHERE {self._key} = :subject AND horizon_id = :horizon"
                    ),
                    {"subject": observation.subject_id, "horizon": observation.horizon_id},
                )
                .mappings()
                .one()
            )
        stored = _from_row(row, self._key)
        if stored.content_identity != observation.content_identity:
            raise ForwardOutcomeConflictError(
                "a different forward outcome is already recorded for this horizon"
            )
        return stored

    def for_subject(self, subject_id: UUID) -> tuple[ForwardOutcomeObservation, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"SELECT {self._columns} FROM {self._table} "
                    f"WHERE {self._key} = :subject ORDER BY due_at, horizon_id"
                ),
                {"subject": subject_id},
            ).mappings()
            return tuple(_from_row(row, self._key) for row in rows)


class PostgresForwardOutcomeRepository:
    """User-tracked forward outcomes. No update or delete path exists by design."""

    def __init__(self, engine: Engine) -> None:
        self._ledger = AppendOnlyOutcomeLedger(
            engine, "forward_outcome_observations", "tracked_candidate_id"
        )

    def append(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        return self._ledger.append(observation)

    def for_candidate(self, candidate_id: UUID) -> tuple[ForwardOutcomeObservation, ...]:
        return self._ledger.for_subject(candidate_id)


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _from_row(row: Any, key_column: str) -> ForwardOutcomeObservation:
    return ForwardOutcomeObservation(
        subject_id=UUID(str(row[key_column])),
        horizon_id=row["horizon_id"],
        status=OutcomeStatus(row["status"]),
        due_at=row["due_at"],
        collected_at=row["collected_at"],
        horizon_policy_version=row["horizon_policy_version"],
        frozen_proposal_identity=row["frozen_proposal_identity"],
        observed_at=row["observed_at"],
        underlying_price=_decimal(row["underlying_price"]),
        modeled_mark=_decimal(row["modeled_mark"]),
        modeled_pnl=_decimal(row["modeled_pnl"]),
        mark_basis=row["mark_basis"],
        mark_model_version=row["mark_model_version"],
        unknown_reasons=tuple(json.loads(row["unknown_reasons_json"])),
        provenance=tuple(json.loads(row["provenance_json"])),
        content_identity=row["content_identity"],
    )
