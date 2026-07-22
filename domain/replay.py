"""Immutable analytical execution replay records."""

from dataclasses import dataclass

from domain.execution import ExecutionPlan, ExecutionPlanningLifecycle, PortfolioDelta
from domain.operational import PortfolioSnapshot
from domain.references import EvidenceReference
from domain.simulation import SimulationMarketData, SimulationResult


@dataclass(frozen=True, slots=True)
class ExecutionReplayRecord:
    execution_replay_id: str
    replay_algorithm_version: str
    execution_plan: ExecutionPlan
    simulation_market_data: SimulationMarketData
    expected_simulation_result: SimulationResult
    expected_simulated_delta: PortfolioDelta
    expected_next_snapshot: PortfolioSnapshot
    expected_lifecycle: ExecutionPlanningLifecycle
    input_digest: str
    output_digest: str
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    replay_verification_id: str
    replay_algorithm_version: str
    execution_replay_id: str
    verified: bool
    actual_output_digest: str
    mismatch_reasons: tuple[str, ...]
