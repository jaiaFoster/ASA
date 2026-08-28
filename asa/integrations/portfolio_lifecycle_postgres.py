from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from asa.contracts.portfolio_lifecycle import (
    PositionAssociation,
    PositionLifecycleObservation,
    PositionLifecycleState,
    TrackedCandidate,
)


class PostgresPortfolioLifecycleRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_candidate(self, candidate: TrackedCandidate) -> TrackedCandidate:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO tracked_candidates (
                        id, originating_observation_id, opportunity_id, signal_id,
                        signal_version, symbol, tracked_at, originating_observed_at,
                        evidence_observed_at, exact_option_symbols
                    ) VALUES (
                        :id, :originating_observation_id, :opportunity_id, :signal_id,
                        :signal_version, :symbol, :tracked_at, :originating_observed_at,
                        :evidence_observed_at, :exact_option_symbols
                    ) ON CONFLICT (originating_observation_id) DO NOTHING
                """),
                {
                    "id": candidate.id,
                    "originating_observation_id": candidate.originating_observation_id,
                    "opportunity_id": candidate.opportunity_id,
                    "signal_id": candidate.strategy_id,
                    "signal_version": candidate.strategy_version,
                    "symbol": candidate.symbol,
                    "tracked_at": candidate.tracked_at,
                    "originating_observed_at": candidate.originating_observed_at,
                    "evidence_observed_at": candidate.evidence_observed_at,
                    "exact_option_symbols": list(candidate.exact_option_symbols),
                },
            )
        stored = self.candidate(candidate.id)
        if stored is None:
            raise RuntimeError("tracked candidate could not be read after insertion")
        return stored

    def candidates(self) -> tuple[TrackedCandidate, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text("SELECT * FROM tracked_candidates ORDER BY tracked_at, id")
            ).mappings()
            return tuple(_candidate(row) for row in rows)

    def candidate(self, candidate_id: UUID) -> TrackedCandidate | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM tracked_candidates WHERE id = :id"),
                    {"id": candidate_id},
                )
                .mappings()
                .first()
            )
            return None if row is None else _candidate(row)

    def append_association(self, association: PositionAssociation) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO portfolio_position_associations (
                        tracked_candidate_id, broker_position_key, state, observed_at
                    ) VALUES (
                        :tracked_candidate_id, :broker_position_key, :state, :observed_at
                    ) ON CONFLICT DO NOTHING
                """),
                {
                    "tracked_candidate_id": association.tracked_candidate_id,
                    "broker_position_key": association.broker_position_key,
                    "state": association.state.value,
                    "observed_at": association.observed_at,
                },
            )

    def append_lifecycle_observation(self, observation: PositionLifecycleObservation) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO portfolio_lifecycle_observations (
                        tracked_candidate_id, state, broker_position_key,
                        broker_observed_at, strategy_result_observed_at,
                        evidence_observed_at
                    ) VALUES (
                        :tracked_candidate_id, :state, :broker_position_key,
                        :broker_observed_at, :strategy_result_observed_at,
                        :evidence_observed_at
                    ) ON CONFLICT DO NOTHING
                """),
                {
                    "tracked_candidate_id": observation.tracked_candidate_id,
                    "state": observation.state.value,
                    "broker_position_key": observation.broker_position_key,
                    "broker_observed_at": observation.broker_observed_at,
                    "strategy_result_observed_at": observation.strategy_result_observed_at,
                    "evidence_observed_at": observation.evidence_observed_at,
                },
            )

    def lifecycle_observations(
        self, candidate_id: UUID
    ) -> tuple[PositionLifecycleObservation, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text("""
                    SELECT * FROM portfolio_lifecycle_observations
                    WHERE tracked_candidate_id = :candidate_id
                    ORDER BY broker_observed_at, id
                """),
                {"candidate_id": candidate_id},
            ).mappings()
            return tuple(_lifecycle_observation(row) for row in rows)


def _candidate(row: RowMapping) -> TrackedCandidate:
    return TrackedCandidate(
        id=row["id"],
        originating_observation_id=row["originating_observation_id"],
        opportunity_id=row["opportunity_id"],
        strategy_id=row["signal_id"],
        strategy_version=row["signal_version"],
        symbol=row["symbol"],
        tracked_at=row["tracked_at"],
        originating_observed_at=row["originating_observed_at"],
        evidence_observed_at=row["evidence_observed_at"],
        exact_option_symbols=tuple(row["exact_option_symbols"]),
    )


def _lifecycle_observation(row: RowMapping) -> PositionLifecycleObservation:
    return PositionLifecycleObservation(
        tracked_candidate_id=row["tracked_candidate_id"],
        state=PositionLifecycleState(row["state"]),
        broker_position_key=row["broker_position_key"],
        broker_observed_at=row["broker_observed_at"],
        strategy_result_observed_at=row["strategy_result_observed_at"],
        evidence_observed_at=row["evidence_observed_at"],
    )
