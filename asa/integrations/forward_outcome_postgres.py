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

_COLUMNS = (
    "tracked_candidate_id, horizon_id, status, due_at, collected_at, "
    "horizon_policy_version, frozen_proposal_identity, observed_at, underlying_price, "
    "modeled_mark, modeled_pnl, mark_basis, mark_model_version, unknown_reasons_json, "
    "provenance_json, content_identity"
)


class PostgresForwardOutcomeRepository:
    """No update or delete path exists by design."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(self, observation: ForwardOutcomeObservation) -> ForwardOutcomeObservation:
        params = {
            "tracked_candidate_id": observation.tracked_candidate_id,
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
                    f"INSERT INTO forward_outcome_observations ({_COLUMNS}) VALUES ("
                    + ", ".join(f":{name.strip()}" for name in _COLUMNS.split(","))
                    + ") ON CONFLICT (tracked_candidate_id, horizon_id) DO NOTHING"
                ),
                params,
            )
            row = (
                connection.execute(
                    text(
                        f"SELECT {_COLUMNS} FROM forward_outcome_observations "
                        "WHERE tracked_candidate_id = :candidate AND horizon_id = :horizon"
                    ),
                    {
                        "candidate": observation.tracked_candidate_id,
                        "horizon": observation.horizon_id,
                    },
                )
                .mappings()
                .one()
            )
        stored = _from_row(row)
        if stored.content_identity != observation.content_identity:
            raise ForwardOutcomeConflictError(
                "a different forward outcome is already recorded for this horizon"
            )
        return stored

    def for_candidate(self, candidate_id: UUID) -> tuple[ForwardOutcomeObservation, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"SELECT {_COLUMNS} FROM forward_outcome_observations "
                    "WHERE tracked_candidate_id = :candidate ORDER BY due_at, horizon_id"
                ),
                {"candidate": candidate_id},
            ).mappings()
            return tuple(_from_row(row) for row in rows)


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _from_row(row: Any) -> ForwardOutcomeObservation:
    return ForwardOutcomeObservation(
        tracked_candidate_id=UUID(str(row["tracked_candidate_id"])),
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
