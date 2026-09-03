import json
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from asa.contracts.portfolio_lifecycle import (
    ExecutionReadinessArtifact,
    PositionAssociation,
    PositionLifecycleObservation,
    PositionLifecycleState,
    ReconciliationState,
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
                        evidence_observed_at, exact_option_symbols,
                        resolved_proposal_identity, resolved_proposal_json
                    ) VALUES (
                        :id, :originating_observation_id, :opportunity_id, :signal_id,
                        :signal_version, :symbol, :tracked_at, :originating_observed_at,
                        :evidence_observed_at, :exact_option_symbols,
                        :resolved_proposal_identity, :resolved_proposal_json
                    ) ON CONFLICT (originating_observation_id) DO NOTHING
                """),
                _candidate_params(candidate),
            )
        stored = self.candidate(candidate.id)
        if stored is None:
            raise RuntimeError("tracked candidate could not be read after insertion")
        return stored

    def put_execution_readiness(self, artifact: ExecutionReadinessArtifact) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO execution_readiness_artifacts (
                        originating_observation_id, signal_id, symbol,
                        assessment_identity, canonical_json, assessment_json, assessed_at
                    ) VALUES (
                        :originating_observation_id, :signal_id, :symbol,
                        :assessment_identity, :canonical_json, :assessment_json, :assessed_at
                    ) ON CONFLICT (signal_id, symbol) DO UPDATE SET
                        originating_observation_id = EXCLUDED.originating_observation_id,
                        assessment_identity = EXCLUDED.assessment_identity,
                        canonical_json = EXCLUDED.canonical_json,
                        assessment_json = EXCLUDED.assessment_json,
                        assessed_at = EXCLUDED.assessed_at
                    WHERE execution_readiness_artifacts.assessed_at <= EXCLUDED.assessed_at
                """),
                {
                    "originating_observation_id": artifact.originating_observation_id,
                    "signal_id": artifact.strategy_id,
                    "symbol": artifact.symbol,
                    "assessment_identity": artifact.assessment_identity,
                    "canonical_json": artifact.canonical_json,
                    "assessment_json": artifact.assessment_json,
                    "assessed_at": artifact.assessed_at,
                },
            )

    def execution_readiness(
        self, strategy_id: str, symbol: str
    ) -> ExecutionReadinessArtifact | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("""
                        SELECT * FROM execution_readiness_artifacts
                        WHERE signal_id = :signal_id AND symbol = :symbol
                    """),
                    {"signal_id": strategy_id, "symbol": symbol.upper()},
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return ExecutionReadinessArtifact(
            originating_observation_id=row["originating_observation_id"],
            strategy_id=row["signal_id"],
            symbol=row["symbol"],
            assessment_identity=row["assessment_identity"],
            canonical_json=row["canonical_json"],
            assessment_json=row["assessment_json"],
            assessed_at=row["assessed_at"],
        )

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

    def associations(self, candidate_id: UUID) -> tuple[PositionAssociation, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text("""
                    SELECT * FROM portfolio_position_associations
                    WHERE tracked_candidate_id = :candidate_id
                    ORDER BY observed_at, id
                """),
                {"candidate_id": candidate_id},
            ).mappings()
            return tuple(
                PositionAssociation(
                    tracked_candidate_id=row["tracked_candidate_id"],
                    broker_position_key=row["broker_position_key"],
                    state=ReconciliationState(row["state"]),
                    observed_at=row["observed_at"],
                )
                for row in rows
            )


def _candidate_params(candidate: TrackedCandidate) -> dict[str, object]:
    """Encode JSONB explicitly for raw ``text()`` SQL.

    psycopg cannot infer that a plain Python list targets JSONB when SQLAlchemy
    has no column metadata, so passing the list directly is interpreted as a
    PostgreSQL array and rejected as invalid JSON.
    """
    return {
        "id": candidate.id,
        "originating_observation_id": candidate.originating_observation_id,
        "opportunity_id": candidate.opportunity_id,
        "signal_id": candidate.strategy_id,
        "signal_version": candidate.strategy_version,
        "symbol": candidate.symbol,
        "tracked_at": candidate.tracked_at,
        "originating_observed_at": candidate.originating_observed_at,
        "evidence_observed_at": candidate.evidence_observed_at,
        "exact_option_symbols": json.dumps(candidate.exact_option_symbols),
        "resolved_proposal_identity": candidate.resolved_proposal_identity,
        "resolved_proposal_json": candidate.resolved_proposal_json,
    }


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
        resolved_proposal_identity=row["resolved_proposal_identity"],
        resolved_proposal_json=row["resolved_proposal_json"],
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
