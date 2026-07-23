"""Postgres-backed ObservationHistoryRepository (SPRINT-009R/EPIC-R3).

Implements strategy_runtime.persistence.ObservationHistoryRepository --
raw SQL through sqlalchemy.Engine/text(), no ORM, matching this codebase's
established PostgresLatestResultRepository pattern
(asa/integrations/universal_screening_postgres.py) exactly. append() only
ever inserts a new row -- there is no update or delete path anywhere in
this module, enforcing "append-only" structurally, not merely by
convention. history_for() reconstructs the full, ordered
strategy_runtime.lifecycle.OpportunityHistory for one opportunity_id, or
None if that opportunity has never been observed.
"""

from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from strategy_runtime.lifecycle import (
    OpportunityHistory,
    OpportunityObservation,
    RecommendedAction,
)


class PostgresObservationHistoryRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(self, observation: OpportunityObservation) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO opportunity_observation_history (
                        opportunity_id, signal_id, symbol, lifecycle_stage,
                        verdict, recommended_action, observed_at
                    ) VALUES (
                        :opportunity_id, :signal_id, :symbol, :lifecycle_stage,
                        :verdict, :recommended_action, :observed_at
                    )
                """),
                {
                    "opportunity_id": observation.opportunity_id,
                    "signal_id": observation.strategy_id,
                    "symbol": observation.symbol,
                    "lifecycle_stage": observation.lifecycle_stage,
                    "verdict": observation.verdict,
                    "recommended_action": observation.recommended_action.value,
                    "observed_at": observation.observed_at,
                },
            )

    def history_for(self, opportunity_id: str) -> OpportunityHistory | None:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT * FROM opportunity_observation_history "
                    "WHERE opportunity_id = :opportunity_id ORDER BY observed_at"
                ),
                {"opportunity_id": opportunity_id},
            ).mappings()
            observations = tuple(_to_observation(row) for row in rows)
            return OpportunityHistory(opportunity_id, observations) if observations else None


def _to_observation(mapping: RowMapping) -> OpportunityObservation:
    return OpportunityObservation(
        opportunity_id=mapping["opportunity_id"],
        strategy_id=mapping["signal_id"],
        symbol=mapping["symbol"],
        lifecycle_stage=mapping["lifecycle_stage"],
        verdict=mapping["verdict"],
        recommended_action=RecommendedAction(mapping["recommended_action"]),
        observed_at=mapping["observed_at"],
    )
