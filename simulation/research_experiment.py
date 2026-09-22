"""Minimal immutable identity contract for reproducible research experiments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date

_SCHEMA = "asa.research_experiment/v1"


def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _identity(payload: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ResearchExperiment:
    experiment_id: str
    strategy_id: str
    strategy_version: str
    strategy_checksum: str
    evidence_identity: str
    universe_identity: str
    formula_versions: tuple[str, ...]
    parameters: tuple[tuple[str, str], ...]
    period_start: date
    period_end: date
    temporal_convention: str
    defensive_representation: str
    transaction_cost_assumption: str
    benchmark_id: str
    code_sha: str
    preregistration_identity: str

    def __post_init__(self) -> None:
        required = (
            self.strategy_id,
            self.strategy_version,
            self.strategy_checksum,
            self.evidence_identity,
            self.universe_identity,
            self.temporal_convention,
            self.defensive_representation,
            self.transaction_cost_assumption,
            self.benchmark_id,
            self.code_sha,
            self.preregistration_identity,
        )
        if any(not value or value != value.strip() for value in required):
            raise ValueError("research experiment identity fields must be non-empty")
        if self.period_end < self.period_start:
            raise ValueError("research experiment period end precedes start")
        if tuple(sorted(set(self.formula_versions))) != self.formula_versions:
            raise ValueError("formula versions must be sorted and unique")
        if tuple(sorted(dict(self.parameters).items())) != self.parameters:
            raise ValueError("parameters must be sorted with unique names")


def _experiment_payload(experiment: ResearchExperiment) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA,
        "strategy_id": experiment.strategy_id,
        "strategy_version": experiment.strategy_version,
        "strategy_checksum": experiment.strategy_checksum,
        "evidence_identity": experiment.evidence_identity,
        "universe_identity": experiment.universe_identity,
        "formula_versions": list(experiment.formula_versions),
        "parameters": [list(item) for item in experiment.parameters],
        "period": [experiment.period_start.isoformat(), experiment.period_end.isoformat()],
        "temporal_convention": experiment.temporal_convention,
        "defensive_representation": experiment.defensive_representation,
        "transaction_cost_assumption": experiment.transaction_cost_assumption,
        "benchmark_id": experiment.benchmark_id,
        "code_sha": experiment.code_sha,
        "preregistration_identity": experiment.preregistration_identity,
    }


def build_research_experiment(
    *,
    strategy_id: str,
    strategy_version: str,
    strategy_checksum: str,
    evidence_identity: str,
    universe_identity: str,
    formula_versions: tuple[str, ...],
    parameters: tuple[tuple[str, str], ...],
    period_start: date,
    period_end: date,
    temporal_convention: str,
    defensive_representation: str,
    transaction_cost_assumption: str,
    benchmark_id: str,
    code_sha: str,
    preregistration_identity: str,
) -> ResearchExperiment:
    provisional = ResearchExperiment(
        "pending",
        strategy_id,
        strategy_version,
        strategy_checksum,
        evidence_identity,
        universe_identity,
        tuple(sorted(set(formula_versions))),
        tuple(sorted(parameters)),
        period_start,
        period_end,
        temporal_convention,
        defensive_representation,
        transaction_cost_assumption,
        benchmark_id,
        code_sha,
        preregistration_identity,
    )
    return replace(provisional, experiment_id=_identity(_experiment_payload(provisional)))


def serialize_research_experiment(experiment: ResearchExperiment) -> str:
    payload = _experiment_payload(experiment)
    payload["experiment_id"] = experiment.experiment_id
    return _canonical(payload)


def deserialize_research_experiment(serialized: str) -> ResearchExperiment:
    payload = json.loads(serialized)
    if payload.get("schema_version") != _SCHEMA:
        raise ValueError("unsupported research experiment schema")
    experiment = ResearchExperiment(
        payload["experiment_id"],
        payload["strategy_id"],
        payload["strategy_version"],
        payload["strategy_checksum"],
        payload["evidence_identity"],
        payload["universe_identity"],
        tuple(payload["formula_versions"]),
        tuple((str(name), str(value)) for name, value in payload["parameters"]),
        date.fromisoformat(payload["period"][0]),
        date.fromisoformat(payload["period"][1]),
        payload["temporal_convention"],
        payload["defensive_representation"],
        payload["transaction_cost_assumption"],
        payload["benchmark_id"],
        payload["code_sha"],
        payload["preregistration_identity"],
    )
    if experiment.experiment_id != _identity(_experiment_payload(experiment)):
        raise ValueError("research experiment identity does not match its contents")
    if serialize_research_experiment(experiment) != serialized:
        raise ValueError("research experiment serialization is not canonical")
    return experiment


def research_result_identity(
    experiment: ResearchExperiment,
    *,
    return_series_identity: str,
    metric_values: tuple[tuple[str, str], ...],
) -> str:
    if not return_series_identity:
        raise ValueError("return series identity is required")
    if tuple(sorted(dict(metric_values).items())) != metric_values:
        raise ValueError("metric values must be sorted with unique names")
    return _identity(
        {
            "schema_version": "asa.research_result/v1",
            "experiment_id": experiment.experiment_id,
            "return_series_identity": return_series_identity,
            "metric_values": [list(item) for item in metric_values],
        }
    )
