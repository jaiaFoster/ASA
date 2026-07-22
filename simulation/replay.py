"""Canonical analytical execution serialization and replay verification."""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from domain.canonicalization import serialize_canonical
from domain.execution import ExecutionPlan, ExecutionPlanningLifecycle, PortfolioDelta
from domain.operational import PortfolioSnapshot
from domain.replay import ExecutionReplayRecord, ReplayVerification
from domain.references import EvidenceReference
from domain.simulation import SimulationMarketData, SimulationResult
from portfolio.engine import apply_simulation
from simulation.engine import simulate
from simulation.lifecycle import complete_lifecycle

REPLAY_ALGORITHM_VERSION = "v1"


def _normalized(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(
            sorted(
                (
                    ("__type__", type(value).__qualname__),
                    *((field.name, _normalized(getattr(value, field.name))) for field in dataclasses.fields(value)),
                ),
                key=lambda item: item[0],
            )
        )
    if isinstance(value, Enum):
        return (("__enum__", type(value).__qualname__), ("value", _normalized(value.value)))
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, tuple):
        return tuple(_normalized(item) for item in value)
    if value is None or type(value) in {bool, int, float, Decimal, str}:
        return value
    raise TypeError(f"unsupported replay value: {type(value).__qualname__}")


def canonical_replay_bytes(value: object) -> bytes:
    return serialize_canonical(_normalized(value)).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_replay_bytes(value)).hexdigest()


def _evidence(*groups: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    unique = {(item.kind.value, item.referenced_id, item.version): item for group in groups for item in group}
    return tuple(unique[key] for key in sorted(unique))


def record_replay(
    plan: ExecutionPlan,
    market_data: SimulationMarketData,
    result: SimulationResult,
    delta: PortfolioDelta,
    snapshot: PortfolioSnapshot,
    lifecycle: ExecutionPlanningLifecycle,
) -> ExecutionReplayRecord:
    inputs = (plan, market_data)
    outputs = (result, delta, snapshot, lifecycle)
    input_digest = _digest(inputs)
    output_digest = _digest(outputs)
    evidence = _evidence(plan.evidence, market_data.evidence, result.evidence, delta.evidence, snapshot.evidence, lifecycle.evidence)
    replay_id = _digest((REPLAY_ALGORITHM_VERSION, input_digest, output_digest, evidence))
    return ExecutionReplayRecord(
        replay_id, REPLAY_ALGORITHM_VERSION, plan, market_data, result, delta, snapshot,
        lifecycle, input_digest, output_digest, evidence,
    )


def verify_replay(record: ExecutionReplayRecord) -> ReplayVerification:
    result = simulate(record.execution_plan, record.simulation_market_data)
    delta, snapshot = apply_simulation(record.execution_plan, result, record.simulation_market_data)
    prefix_count = len(record.expected_lifecycle.events) - len(result.ordered_order_states) - 3
    prefix = ExecutionPlanningLifecycle(
        "replay-prefix", record.expected_lifecycle.lifecycle_algorithm_version,
        record.expected_lifecycle.root_risk_decision_id,
        record.expected_lifecycle.events[:prefix_count], record.expected_lifecycle.evidence,
    )
    lifecycle = complete_lifecycle(prefix, result, delta, snapshot)
    actual_digest = _digest((result, delta, snapshot, lifecycle))
    reasons: list[str] = []
    if _digest((record.execution_plan, record.simulation_market_data)) != record.input_digest:
        reasons.append("input digest mismatch")
    if actual_digest != record.output_digest:
        reasons.append("output digest mismatch")
    verified = not reasons
    verification_id = _digest((REPLAY_ALGORITHM_VERSION, record.execution_replay_id, verified, actual_digest, tuple(reasons)))
    return ReplayVerification(
        verification_id, REPLAY_ALGORITHM_VERSION, record.execution_replay_id,
        verified, actual_digest, tuple(reasons),
    )
