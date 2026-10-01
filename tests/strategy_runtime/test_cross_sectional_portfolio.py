from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from analytics.quantile_assignment import QuantilePolicy
from domain import OptionLeg, OptionLegPosition, UnknownReason
from strategy_runtime.cross_sectional_portfolio import (
    PortfolioBookSide,
    PortfolioWeightPolicy,
    build_cross_sectional_portfolio,
    build_delta_hedged_option_position,
)
from tests.strategies.test_cboe_put_strategy import _put


def test_p10_exact_short_call_like_leg_gets_static_long_delta_hedge() -> None:
    contract = _put(Decimal("100"))
    leg = OptionLeg(contract, OptionLegPosition.SHORT, Decimal(2), "written_option")
    result = build_delta_hedged_option_position("AAA", leg, contract_multiplier=Decimal(100))
    assert not isinstance(result, UnknownReason)
    assert result.underlying_quantity == contract.delta * Decimal(200)
    assert (
        result.identity
        == build_delta_hedged_option_position("AAA", leg, contract_multiplier=Decimal(100)).identity
    )


def test_p10_missing_delta_is_typed_unknown() -> None:
    contract = _put(Decimal("100"))
    contract = replace(contract, delta=None)
    leg = OptionLeg(contract, OptionLegPosition.LONG, Decimal(1), "option")
    assert build_delta_hedged_option_position(
        "AAA", leg, contract_multiplier=Decimal(100)
    ) == UnknownReason("missing_delta")


@dataclass(frozen=True)
class FixturePosition:
    identity: str


def test_p12_generic_reuse_for_zhan_and_heston_positions_and_equal_weights() -> None:
    values = {"A": Decimal(1), "B": Decimal(2), "C": Decimal(3), "D": UnknownReason("missing")}
    for prefix in ("p10-zhan", "p03-heston"):
        result = build_cross_sectional_portfolio(
            as_of=datetime(2026, 9, 30, tzinfo=UTC),
            evidence_identity="sealed",
            sort_values=values,
            positions={key: FixturePosition(f"{prefix}-{key}") for key in values},
            quantile_policy=QuantilePolicy(groups=3),
            included_quantiles=frozenset({1, 3}),
            weight_policy=PortfolioWeightPolicy.EQUAL,
        )
        assert not isinstance(result, UnknownReason)
        assert {item.subject for item in result.members} == {"A", "C"}
        assert all(item.weight == Decimal("0.5") for item in result.members)
        assert result.quantile_assignment.excluded == (("D", "missing"),)


def test_p12_source_weights_normalize_and_missing_never_ranks() -> None:
    result = build_cross_sectional_portfolio(
        as_of=datetime(2026, 9, 30, tzinfo=UTC),
        evidence_identity="sealed",
        sort_values={"A": Decimal(1), "B": Decimal(2), "X": UnknownReason("unknown")},
        positions={"A": FixturePosition("a"), "B": FixturePosition("b")},
        quantile_policy=QuantilePolicy(groups=2),
        included_quantiles=frozenset({1, 2}),
        weight_policy=PortfolioWeightPolicy.SOURCE_DEFINED,
        source_weights={"A": Decimal(1), "B": Decimal(3)},
    )
    assert not isinstance(result, UnknownReason)
    assert [item.weight for item in result.members] == [Decimal("0.25"), Decimal("0.75")]


def test_p12_three_member_repeating_weights_close_with_deterministic_residual() -> None:
    values = {key: Decimal(index) for index, key in enumerate(("A", "B", "C"), 1)}
    positions = {key: FixturePosition(key.lower()) for key in values}
    for policy, source_weights in (
        (PortfolioWeightPolicy.EQUAL, None),
        (PortfolioWeightPolicy.SOURCE_DEFINED, {key: Decimal(1) for key in values}),
    ):
        result = build_cross_sectional_portfolio(
            as_of=datetime(2026, 9, 30, tzinfo=UTC),
            evidence_identity="sealed",
            sort_values=values,
            positions=positions,
            quantile_policy=QuantilePolicy(groups=3),
            included_quantiles=frozenset({1, 2, 3}),
            weight_policy=policy,
            source_weights=source_weights,
        )
        assert not isinstance(result, UnknownReason)
        assert sum((item.weight for item in result.members), Decimal(0)) == Decimal(1)
        assert result.members[-1].subject == "C"


def test_p12_source_residual_uses_largest_weight_without_zeroing_tiny_member() -> None:
    result = build_cross_sectional_portfolio(
        as_of=datetime(2026, 9, 30, tzinfo=UTC),
        evidence_identity="sealed",
        sort_values={"A": Decimal(1), "B": Decimal(2), "C": Decimal(3)},
        positions={key: FixturePosition(key.lower()) for key in ("A", "B", "C")},
        quantile_policy=QuantilePolicy(groups=3),
        included_quantiles=frozenset({1, 2, 3}),
        weight_policy=PortfolioWeightPolicy.SOURCE_DEFINED,
        source_weights={"A": Decimal(1), "B": Decimal(1), "C": Decimal("1e-100")},
    )
    assert not isinstance(result, UnknownReason)
    weights = {item.subject: item.weight for item in result.members}
    assert weights["C"] > 0
    assert sum(weights.values(), Decimal(0)) == Decimal(1)


def test_p12_long_short_books_normalize_each_side_and_preserve_direction_in_identity() -> None:
    kwargs = dict(
        as_of=datetime(2026, 9, 30, tzinfo=UTC),
        evidence_identity="sealed",
        sort_values={"HIGH": Decimal(1), "LOW": Decimal(2)},
        positions={"HIGH": FixturePosition("long"), "LOW": FixturePosition("short")},
        quantile_policy=QuantilePolicy(groups=2),
        included_quantiles=frozenset({1, 2}),
        weight_policy=PortfolioWeightPolicy.SOURCE_DEFINED,
        source_weights={"HIGH": Decimal(9), "LOW": Decimal(3)},
    )
    result = build_cross_sectional_portfolio(**kwargs, short_quantiles=frozenset({2}))
    all_long = build_cross_sectional_portfolio(**kwargs)
    assert not isinstance(result, UnknownReason) and not isinstance(all_long, UnknownReason)
    assert [(item.side, item.weight) for item in result.members] == [
        (PortfolioBookSide.LONG, Decimal(1)),
        (PortfolioBookSide.SHORT, Decimal(1)),
    ]
    assert result.identity != all_long.identity
