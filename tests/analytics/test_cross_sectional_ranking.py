from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from analytics.cross_sectional_ranking import (
    EligibilityState,
    RankableFact,
    RankingDirection,
    UnrankableSubject,
    rank_named_facts,
    strictly_above_trend,
    top_ranked,
)
from domain import CanonicalInstrumentIdentity

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _fact(symbol: str, value: str) -> RankableFact:
    return RankableFact(
        CanonicalInstrumentIdentity("symbol", symbol),
        "trailing_12m_total_return",
        "1.0.0",
        f"return:{symbol}",
        Decimal(value),
        NOW,
    )


def test_descending_rank_and_ties_use_canonical_subject_identity() -> None:
    ranking = rank_named_facts((_fact("XLY", "0.1"), _fact("XLF", "0.2"), _fact("XLE", "0.2")))
    assert [(item.rank, item.fact.subject.value) for item in ranking.ranked] == [
        (1, "XLE"), (2, "XLF"), (3, "XLY")
    ]
    assert ranking == rank_named_facts(tuple(reversed(tuple(item.fact for item in ranking.ranked))))


def test_unknown_is_not_ranked_as_an_economic_loss() -> None:
    missing = UnrankableSubject(CanonicalInstrumentIdentity("symbol", "XLC"), "missing_return")
    ranking = rank_named_facts((_fact("XLE", "-0.5"),), unrankable=(missing,))
    assert [item.fact.subject.value for item in ranking.ranked] == ["XLE"]
    assert ranking.unrankable == (missing,)


def test_top_n_is_bounded_and_direction_is_explicit() -> None:
    ranking = rank_named_facts(
        (_fact("XLE", "1"), _fact("XLF", "2"), _fact("XLK", "3")),
        direction=RankingDirection.ASCENDING,
    )
    assert [item.fact.subject.value for item in top_ranked(ranking, 2)] == ["XLE", "XLF"]
    with pytest.raises(ValueError, match="positive"):
        top_ranked(ranking, 0)


def test_trend_pass_fail_equality_and_unknown() -> None:
    assert strictly_above_trend(
        Decimal("101"), Decimal("100"), observation_fact_id="price", sma_fact_id="sma"
    ).state is EligibilityState.PASS
    assert strictly_above_trend(
        Decimal("99"), Decimal("100"), observation_fact_id="price", sma_fact_id="sma"
    ).state is EligibilityState.FAIL
    assert strictly_above_trend(
        Decimal("100"), Decimal("100"), observation_fact_id="price", sma_fact_id="sma"
    ).state is EligibilityState.FAIL
    unknown = strictly_above_trend(
        None, Decimal("100"), observation_fact_id=None, sma_fact_id="sma"
    )
    assert unknown.state is EligibilityState.UNKNOWN
    assert unknown.reason == "missing_trend_evidence"


def test_incomparable_fact_sets_fail_closed() -> None:
    other = RankableFact(
        CanonicalInstrumentIdentity("symbol", "XLK"), "other", "1.0.0", "other:XLK",
        Decimal("1"), NOW,
    )
    with pytest.raises(ValueError, match="share feature"):
        rank_named_facts((_fact("XLE", "1"), other))

