"""Pure reusable Core Component library (STRAT-009)."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from strategies.components import (
    BaseComponent,
    ComponentCategory,
    ComponentDefinition,
    ParameterDefinition,
    PortDefinition,
)
from strategies.errors import ComponentContractError
from strategies.expressions import compile_expression, evaluate_expression
from strategies.manifest import ManifestObject
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue

D = StrategyTypeReference("Decimal", "1.0.0")
B = StrategyTypeReference("Boolean", "1.0.0")
LD = StrategyTypeReference("List", "1.0.0", (D,))
OD = StrategyTypeReference("Optional", "1.0.0", (D,))


def _definition(
    name: str,
    category: ComponentCategory,
    inputs: tuple[PortDefinition, ...],
    outputs: tuple[PortDefinition, ...],
    parameters: tuple[ParameterDefinition, ...] = (),
) -> ComponentDefinition:
    return ComponentDefinition(
        "asa.core",
        name,
        "1.0.0",
        category,
        inputs,
        outputs,
        parameters,
        algorithm_version="1.0.0",
        explanation_template=ManifestObject((("operation", name),)),
    )


class Constant(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "constant",
        ComponentCategory.SOURCE,
        (),
        (PortDefinition("value", D),),
        (ParameterDefinition("value", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("value", parameters.get("value")),))


class Compare(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "compare",
        ComponentCategory.PREDICATE,
        (PortDefinition("left", D), PortDefinition("right", D)),
        (PortDefinition("result", B),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        left = cast(Decimal, inputs.get("left").value)
        right = cast(Decimal, inputs.get("right").value)
        return ComponentValues((("result", TypedValue(B, left >= right)),))


class BooleanAnd(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "boolean_and",
        ComponentCategory.PREDICATE,
        (PortDefinition("left", B), PortDefinition("right", B)),
        (PortDefinition("result", B),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues(
            (("result", TypedValue(B, inputs.get("left").value and inputs.get("right").value)),)
        )


class BooleanOr(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "boolean_or",
        ComponentCategory.PREDICATE,
        (PortDefinition("left", B), PortDefinition("right", B)),
        (PortDefinition("result", B),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues(
            (("result", TypedValue(B, inputs.get("left").value or inputs.get("right").value)),)
        )


class BooleanNot(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "boolean_not",
        ComponentCategory.PREDICATE,
        (PortDefinition("value", B),),
        (PortDefinition("result", B),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("result", TypedValue(B, not inputs.get("value").value)),))


class Clamp(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "clamp",
        ComponentCategory.TRANSFORM,
        (PortDefinition("value", D), PortDefinition("lower", D), PortDefinition("upper", D)),
        (PortDefinition("result", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        value, lower, upper = (
            cast(Decimal, inputs.get(name).value) for name in ("value", "lower", "upper")
        )
        if lower > upper:
            raise ComponentContractError("clamp lower bound exceeds upper bound")
        return ComponentValues((("result", TypedValue(D, min(max(value, lower), upper))),))


class Normalize(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "normalize",
        ComponentCategory.TRANSFORM,
        (PortDefinition("value", D), PortDefinition("lower", D), PortDefinition("upper", D)),
        (PortDefinition("result", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        value, lower, upper = (
            cast(Decimal, inputs.get(name).value) for name in ("value", "lower", "upper")
        )
        if lower >= upper:
            raise ComponentContractError("normalize requires increasing bounds")
        return ComponentValues((("result", TypedValue(D, (value - lower) / (upper - lower))),))


class WeightedScore(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "weighted_score",
        ComponentCategory.SCORE,
        (PortDefinition("values", LD), PortDefinition("weights", LD)),
        (PortDefinition("score", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        values = cast(tuple[Decimal, ...], inputs.get("values").value)
        weights = cast(tuple[Decimal, ...], inputs.get("weights").value)
        if len(values) != len(weights) or not values or sum(weights, Decimal(0)) == 0:
            raise ComponentContractError("weighted score requires aligned nonzero weights")
        score = sum(
            (value * weight for value, weight in zip(values, weights, strict=True)), Decimal(0)
        ) / sum(weights, Decimal(0))
        return ComponentValues((("score", TypedValue(D, score)),))


class Filter(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "filter",
        ComponentCategory.PREDICATE,
        (PortDefinition("include", B), PortDefinition("value", D)),
        (PortDefinition("result", OD),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        value = inputs.get("value").value if inputs.get("include").value else None
        return ComponentValues((("result", TypedValue(OD, value)),))


class Rank(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "rank",
        ComponentCategory.RANK,
        (PortDefinition("values", LD),),
        (PortDefinition("ranked", LD),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        values = cast(tuple[Decimal, ...], inputs.get("values").value)
        return ComponentValues((("ranked", TypedValue(LD, tuple(sorted(values, reverse=True)))),))


class PortfolioConstraint(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "portfolio_constraint",
        ComponentCategory.CONSTRAINT,
        (PortDefinition("allowed", B),),
        (PortDefinition("allowed", B),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("allowed", inputs.get("allowed")),))


class PositionProposal(BaseComponent):
    __slots__ = ()
    definition = _definition(
        "position_proposal",
        ComponentCategory.PROPOSAL,
        (PortDefinition("target_allocation", D),),
        (PortDefinition("target_allocation", D),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        return ComponentValues((("target_allocation", inputs.get("target_allocation")),))


class ExpressionPredicate(BaseComponent):
    """Evaluate a closed expression over two Decimal inputs."""

    __slots__ = ()
    definition = _definition(
        "expression_predicate",
        ComponentCategory.PREDICATE,
        (PortDefinition("left", D), PortDefinition("right", D)),
        (PortDefinition("result", B),),
        (ParameterDefinition("expression", StrategyTypeReference("Text", "1.0.0")),),
    )

    def evaluate(self, inputs: ComponentValues, parameters: ComponentValues) -> ComponentValues:
        source = cast(str, parameters.get("expression").value)
        compiled = compile_expression(source, (("left", D), ("right", D)))
        result = evaluate_expression(compiled, inputs).value
        if result.type_ref != B:
            raise ComponentContractError("expression predicate must produce Boolean")
        return ComponentValues((("result", result),))


CORE_COMPONENTS: tuple[BaseComponent, ...] = (
    Constant(),
    Compare(),
    BooleanAnd(),
    BooleanOr(),
    BooleanNot(),
    Clamp(),
    Normalize(),
    WeightedScore(),
    Filter(),
    Rank(),
    PortfolioConstraint(),
    PositionProposal(),
    ExpressionPredicate(),
)
