from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest

from simulation.research_experiment import (
    build_research_experiment,
    deserialize_research_experiment,
    research_result_identity,
    serialize_research_experiment,
)


def _experiment():
    return build_research_experiment(
        strategy_id="S001",
        strategy_version="1.0.0",
        strategy_checksum="strategy-sha256",
        evidence_identity="evidence-sha256",
        universe_identity="universe-sha256",
        formula_versions=("trailing_12m_total_return@1.0.0", "sma_10m_completed_months@1.0.0"),
        parameters=(("momentum_months", "12"), ("top_n", "3"), ("trend_months", "10")),
        period_start=date(2001, 1, 1),
        period_end=date(2025, 12, 31),
        temporal_convention="completed month; next eligible session",
        defensive_representation="research_asset:us_3_month_treasury_total_return",
        transaction_cost_assumption="10bp per one-way turnover",
        benchmark_id="B1",
        code_sha="a" * 40,
        preregistration_identity="sha256:preregistration",
    )


def test_experiment_identity_and_provider_free_replay_are_deterministic() -> None:
    experiment = _experiment()
    serialized = serialize_research_experiment(experiment)

    assert deserialize_research_experiment(serialized) == experiment
    assert experiment.experiment_id.startswith("sha256:")
    assert (
        build_research_experiment(
            strategy_id=experiment.strategy_id,
            strategy_version=experiment.strategy_version,
            strategy_checksum=experiment.strategy_checksum,
            evidence_identity=experiment.evidence_identity,
            universe_identity=experiment.universe_identity,
            formula_versions=tuple(reversed(experiment.formula_versions)),
            parameters=tuple(reversed(experiment.parameters)),
            period_start=experiment.period_start,
            period_end=experiment.period_end,
            temporal_convention=experiment.temporal_convention,
            defensive_representation=experiment.defensive_representation,
            transaction_cost_assumption=experiment.transaction_cost_assumption,
            benchmark_id=experiment.benchmark_id,
            code_sha=experiment.code_sha,
            preregistration_identity=experiment.preregistration_identity,
        ).experiment_id
        == experiment.experiment_id
    )


def test_tampered_experiment_is_rejected() -> None:
    payload = json.loads(serialize_research_experiment(_experiment()))
    payload["benchmark_id"] = "B3"

    with pytest.raises(ValueError, match="identity does not match"):
        deserialize_research_experiment(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def test_result_identity_covers_experiment_series_and_metrics() -> None:
    experiment = _experiment()
    identity = research_result_identity(
        experiment,
        return_series_identity="sha256:returns",
        metric_values=(("cagr", "0.08"), ("maximum_drawdown", "-0.20")),
    )

    assert identity.startswith("sha256:")
    assert identity != research_result_identity(
        replace(experiment, experiment_id="sha256:different"),
        return_series_identity="sha256:returns",
        metric_values=(("cagr", "0.08"), ("maximum_drawdown", "-0.20")),
    )


def test_invalid_period_and_unsorted_result_metrics_fail_closed() -> None:
    with pytest.raises(ValueError, match="period end precedes start"):
        build_research_experiment(
            strategy_id="S001",
            strategy_version="1.0.0",
            strategy_checksum="checksum",
            evidence_identity="evidence",
            universe_identity="universe",
            formula_versions=(),
            parameters=(),
            period_start=date(2025, 1, 1),
            period_end=date(2024, 1, 1),
            temporal_convention="next session",
            defensive_representation="treasury total return",
            transaction_cost_assumption="10bp",
            benchmark_id="B1",
            code_sha="a" * 40,
            preregistration_identity="prereg",
        )

    with pytest.raises(ValueError, match="metric values must be sorted"):
        research_result_identity(
            _experiment(),
            return_series_identity="returns",
            metric_values=(("z", "1"), ("a", "2")),
        )
