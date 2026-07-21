"""Ranking Engine determinism, filtering, ordering, and identity tests."""

from __future__ import annotations

from datetime import timedelta
from dataclasses import replace
from decimal import Decimal

import pytest

from ranking.engine import rank_opportunities
from ranking.errors import DuplicateOpportunityEvaluationError, InvalidRankingOutputError
from ranking.models import RANKING_ALGORITHM_VERSION, RankingParameters
from tests.ranking.helpers import T0, evaluation


def ids(result):  # type: ignore[no-untyped-def]
    return tuple(item.opportunity.opportunity_id for item in result.ranked_opportunities)


def test_filters_to_pass_evaluations_only() -> None:
    result = rank_opportunities((evaluation("eligible"), evaluation("blocked", eligible=False)))
    assert ids(result) == ("eligible",)


def test_replay_is_byte_for_byte_equal_and_input_order_independent() -> None:
    evaluations = (evaluation("one"), evaluation("two", expected_return="0.05"))
    forward = rank_opportunities(evaluations)
    replay = rank_opportunities(evaluations)
    reversed_input = rank_opportunities(tuple(reversed(evaluations)))
    assert forward == replay == reversed_input


def test_higher_total_score_orders_first() -> None:
    result = rank_opportunities(
        (evaluation("low", expected_return="-0.1"), evaluation("high", expected_return="0.2"))
    )
    assert ids(result) == ("high", "low")


def test_evidence_confidence_is_second_tie_breaker() -> None:
    parameters = RankingParameters(evidence_confidence_weight=Decimal("0"))
    result = rank_opportunities(
        (evaluation("low", confidence=0.2), evaluation("high", confidence=0.9)), parameters
    )
    assert result.ranked_opportunities[0].total_score == result.ranked_opportunities[1].total_score
    assert ids(result) == ("high", "low")


def test_expected_return_is_third_tie_breaker() -> None:
    parameters = RankingParameters(
        expected_return_weight=Decimal("0"), capital_efficiency_weight=Decimal("0")
    )
    result = rank_opportunities(
        (
            evaluation("low", expected_return="0.01"),
            evaluation("high", expected_return="0.20"),
        ),
        parameters,
    )
    assert result.ranked_opportunities[0].total_score == result.ranked_opportunities[1].total_score
    assert ids(result) == ("high", "low")


def test_opportunity_id_is_final_tie_breaker() -> None:
    result = rank_opportunities((evaluation("zeta"), evaluation("alpha")))
    assert ids(result) == ("alpha", "zeta")
    assert tuple(item.rank for item in result.ranked_opportunities) == (1, 2)


def test_rank_identity_excludes_execution_timestamp_and_rank() -> None:
    first = rank_opportunities((evaluation("same", evaluated_at=T0),))
    later = rank_opportunities((evaluation("same", evaluated_at=T0 + timedelta(hours=1)),))
    assert first.ranked_opportunities[0].ranking_id == later.ranked_opportunities[0].ranking_id


def test_effective_parameter_change_changes_identity() -> None:
    base = rank_opportunities((evaluation("same"),))
    changed = rank_opportunities(
        (evaluation("same"),), RankingParameters(expected_return_weight=Decimal("2"))
    )
    assert base.ranked_opportunities[0].ranking_id != changed.ranked_opportunities[0].ranking_id
    assert base.result_id != changed.result_id


def test_identity_and_algorithm_version_are_pinned() -> None:
    result = rank_opportunities((evaluation("vector"),))
    assert RANKING_ALGORITHM_VERSION == "v1"
    assert result.ranking_algorithm_version == "v1"
    assert result.ranked_opportunities[0].ranking_id == (
        "098e9391d988bb0c76f07b2c3e005ea79bcc240a54f8fa7bfad5a9de3812ed01"
    )
    assert result.result_id == "d8d321570bb88ecc3aafd60d0369a223878a3589cfae8e98698cb75e652909a4"
    assert result.ranked_opportunities[0].total_score == Decimal("0.766666666667")


def test_component_regression_vector_is_pinned() -> None:
    components = (
        rank_opportunities((evaluation("vector"),)).ranked_opportunities[0].scoring_components
    )
    assert tuple((item.dimension, item.raw_value, item.score) for item in components) == (
        ("capital_efficiency", Decimal("0.01"), Decimal("1.000000000000")),
        ("downside_risk", Decimal("0.1"), Decimal("0.900000000000")),
        ("evidence_confidence", Decimal("0.8"), Decimal("0.800000000000")),
        ("expected_return", Decimal("0.10"), Decimal("0.700000000000")),
        ("liquidity", Decimal("0.5"), Decimal("0.500000000000")),
        ("opportunity_quality", Decimal("0.7"), Decimal("0.700000000000")),
    )


def test_outputs_are_immutable_and_retain_exact_opportunity() -> None:
    source = evaluation("immutable")
    ranked = rank_opportunities((source,)).ranked_opportunities[0]
    assert ranked.evaluation is source
    assert ranked.opportunity is source.opportunity
    with pytest.raises(Exception):
        ranked.rank = 2


def test_output_model_rejects_invalid_rank() -> None:
    ranked = rank_opportunities((evaluation("invalid-rank"),)).ranked_opportunities[0]
    with pytest.raises(InvalidRankingOutputError):
        replace(ranked, rank=0)


def test_duplicate_opportunity_evaluations_are_rejected() -> None:
    with pytest.raises(DuplicateOpportunityEvaluationError):
        rank_opportunities((evaluation("duplicate"), evaluation("duplicate")))


def test_empty_and_all_failed_inputs_produce_empty_result() -> None:
    assert rank_opportunities(()).ranked_opportunities == ()
    assert rank_opportunities((evaluation("failed", eligible=False),)).ranked_opportunities == ()


def test_every_required_component_and_provenance_is_preserved() -> None:
    ranked = rank_opportunities((evaluation("complete"),)).ranked_opportunities[0]
    assert tuple(item.dimension for item in ranked.scoring_components) == (
        "capital_efficiency",
        "downside_risk",
        "evidence_confidence",
        "expected_return",
        "liquidity",
        "opportunity_quality",
    )
    assert all(component.scorer_version == "v1" for component in ranked.scoring_components)
    assert ranked.effective_parameters
