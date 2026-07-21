"""STRAT-009 Core Component library tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategies.component_registry import ComponentRegistry
from strategies.core_components import (
    B,
    CORE_COMPONENTS,
    D,
    LD,
    BooleanAnd,
    BooleanNot,
    BooleanOr,
    Clamp,
    Compare,
    Constant,
    Filter,
    Normalize,
    PortfolioConstraint,
    PositionProposal,
    Rank,
    WeightedScore,
)
from strategies.manifest import ComponentReference
from strategies.type_system import ComponentValues, TypedValue


def cv(**items: tuple[object, object]) -> ComponentValues:
    return ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in items.items())
    )  # type: ignore[arg-type]


def test_every_required_component_is_registered_and_explainable():
    registry = ComponentRegistry(CORE_COMPONENTS)
    expected = {
        "constant",
        "compare",
        "boolean_and",
        "boolean_or",
        "boolean_not",
        "clamp",
        "normalize",
        "weighted_score",
        "filter",
        "rank",
        "portfolio_constraint",
        "position_proposal",
    }
    assert {item.definition.name for item in CORE_COMPONENTS} == expected
    for name in expected:
        component = registry.resolve(ComponentReference("asa.core", name, "1.0.0"))
        assert component.definition.explanation_template.entries


def test_numeric_components():
    assert Constant().evaluate(ComponentValues(()), cv(value=(D, Decimal("2")))).get(
        "value"
    ).value == Decimal("2")
    assert (
        Compare()
        .evaluate(cv(left=(D, Decimal("2")), right=(D, Decimal("1"))), ComponentValues(()))
        .get("result")
        .value
        is True
    )
    assert Clamp().evaluate(
        cv(value=(D, Decimal("4")), lower=(D, Decimal("0")), upper=(D, Decimal("3"))),
        ComponentValues(()),
    ).get("result").value == Decimal("3")
    assert Normalize().evaluate(
        cv(value=(D, Decimal("5")), lower=(D, Decimal("0")), upper=(D, Decimal("10"))),
        ComponentValues(()),
    ).get("result").value == Decimal("0.5")
    assert WeightedScore().evaluate(
        cv(values=(LD, (Decimal("1"), Decimal("0"))), weights=(LD, (Decimal("3"), Decimal("1")))),
        ComponentValues(()),
    ).get("score").value == Decimal("0.75")


def test_logical_filter_rank_and_portfolio_components():
    assert (
        BooleanAnd()
        .evaluate(cv(left=(B, True), right=(B, False)), ComponentValues(()))
        .get("result")
        .value
        is False
    )
    assert (
        BooleanOr()
        .evaluate(cv(left=(B, True), right=(B, False)), ComponentValues(()))
        .get("result")
        .value
        is True
    )
    assert (
        BooleanNot().evaluate(cv(value=(B, True)), ComponentValues(())).get("result").value is False
    )
    assert (
        Filter()
        .evaluate(cv(include=(B, False), value=(D, Decimal("2"))), ComponentValues(()))
        .get("result")
        .value
        is None
    )
    assert Rank().evaluate(cv(values=(LD, (Decimal("1"), Decimal("3")))), ComponentValues(())).get(
        "ranked"
    ).value == (Decimal("3"), Decimal("1"))
    assert (
        PortfolioConstraint()
        .evaluate(cv(allowed=(B, True)), ComponentValues(()))
        .get("allowed")
        .value
        is True
    )
    assert PositionProposal().evaluate(
        cv(target_allocation=(D, Decimal("0.1"))), ComponentValues(())
    ).get("target_allocation").value == Decimal("0.1")


@pytest.mark.parametrize("component", CORE_COMPONENTS)
def test_components_are_stateless(component: object):
    assert not hasattr(component, "__dict__")
