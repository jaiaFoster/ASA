"""Individual Ranking v1 component and numeric-boundary tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ranking.errors import InvalidRankingParameterError
from ranking.models import RankingParameters
from ranking.scorers import (
    score_capital_efficiency,
    score_downside_risk,
    score_evidence_confidence,
    score_expected_return,
    score_liquidity,
    score_opportunity_quality,
)
from tests.ranking.helpers import evaluation


def opportunity(**kwargs):  # type: ignore[no-untyped-def]
    return evaluation("score", **kwargs).opportunity


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("-0.25", Decimal("0")), ("0", Decimal("0.5")), ("0.25", Decimal("1")), ("2", Decimal("1"))],
)
def test_expected_return_boundaries(raw: str, expected: Decimal) -> None:
    assert (
        score_expected_return(opportunity(expected_return=raw), RankingParameters()).score
        == expected
    )


def test_downside_risk_is_loss_to_capital_ratio() -> None:
    assert score_downside_risk(opportunity(maximum_loss="0"), RankingParameters()).score == Decimal(
        "1"
    )
    assert score_downside_risk(
        opportunity(maximum_loss="-100", capital_required="100"), RankingParameters()
    ).score == Decimal("0")


def test_zero_capital_downside_boundary_is_deterministic() -> None:
    assert score_downside_risk(
        opportunity(maximum_loss="0", capital_required="0"), RankingParameters()
    ).score == Decimal("1")


def test_evidence_confidence_preserves_decimal_value() -> None:
    component = score_evidence_confidence(opportunity(confidence=0.73), RankingParameters())
    assert component.raw_value == Decimal("0.73")
    assert component.score == Decimal("0.73")


def test_capital_efficiency_uses_return_per_day() -> None:
    component = score_capital_efficiency(
        opportunity(expected_return="0.1", horizon_days=10), RankingParameters()
    )
    assert component.raw_value == Decimal("0.01")
    assert component.score == Decimal("1")
    assert component.assumptions


def test_liquidity_placeholder_is_explicit_and_configurable() -> None:
    component = score_liquidity(
        opportunity(), RankingParameters(liquidity_placeholder_score=Decimal("0.4"))
    )
    assert component.score == Decimal("0.4")
    assert "placeholder" in component.assumptions[0]


def test_quality_prefers_probability_when_present() -> None:
    actual = score_opportunity_quality(opportunity(probability="0.8"), RankingParameters())
    fallback = score_opportunity_quality(opportunity(probability=None), RankingParameters())
    assert actual.score == Decimal("0.8") and actual.assumptions == ()
    assert fallback.score == Decimal("0.5") and fallback.assumptions


@pytest.mark.parametrize(
    "parameters",
    [
        RankingParameters(expected_return_weight=Decimal("0")),
        RankingParameters(liquidity_placeholder_score=Decimal("0")),
        RankingParameters(quality_placeholder_score=Decimal("1")),
    ],
)
def test_valid_parameter_boundaries(parameters: RankingParameters) -> None:
    assert parameters.canonical_items()


def test_invalid_parameter_boundaries_are_rejected() -> None:
    with pytest.raises(InvalidRankingParameterError):
        RankingParameters(expected_return_floor=Decimal("1"), expected_return_ceiling=Decimal("1"))
    with pytest.raises(InvalidRankingParameterError):
        RankingParameters(liquidity_placeholder_score=Decimal("1.1"))
    with pytest.raises(InvalidRankingParameterError):
        RankingParameters(expected_return_weight=Decimal("-1"))
    with pytest.raises(InvalidRankingParameterError):
        RankingParameters(
            expected_return_weight=Decimal("0"),
            downside_risk_weight=Decimal("0"),
            evidence_confidence_weight=Decimal("0"),
            capital_efficiency_weight=Decimal("0"),
            liquidity_weight=Decimal("0"),
            opportunity_quality_weight=Decimal("0"),
        )
