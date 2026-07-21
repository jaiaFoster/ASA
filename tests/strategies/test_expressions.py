"""STRAT-007 deterministic Expression Language regression vectors."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, timedelta
from decimal import Decimal

import pytest

from strategies.expressions import compile_expression, evaluate_expression
from strategies.errors import ExpressionCompileError, ExpressionEvaluationError
from strategies.type_system import ComponentValues, StrategyTypeReference, TypedValue


def ref(name: str, *arguments: StrategyTypeReference) -> StrategyTypeReference:
    return StrategyTypeReference(name, "1.0.0", arguments)


def values(**items: tuple[StrategyTypeReference, object]) -> ComponentValues:
    return ComponentValues(
        tuple((name, TypedValue(type_ref, value)) for name, (type_ref, value) in items.items())
    )


def test_whitespace_has_one_canonical_identity():
    inputs = (("price", ref("Decimal")),)
    assert (
        compile_expression("price+1.25", inputs).expression_id
        == compile_expression(" price + 1.25 ", inputs).expression_id
    )


def test_compiled_contract_is_immutable_and_replayable():
    compiled = compile_expression("amount * 2", (("amount", ref("Integer")),))
    with pytest.raises(FrozenInstanceError):
        compiled.expression_id = "changed"  # type: ignore[misc]
    first = evaluate_expression(compiled, values(amount=(ref("Integer"), 4)))
    second = evaluate_expression(compiled, values(amount=(ref("Integer"), 4)))
    assert first == second
    assert first.value.value == 8


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("missing + 1", "unknown_identifier"),
        ("1 < 2 < 3", "syntax"),
        ('open("x")', "unknown_function"),
        ("1 / 2", "type"),
        ("duration(days: 1) * duration(days: 2)", "type"),
    ],
)
def test_invalid_programs_fail_closed(source: str, code: str):
    with pytest.raises(ExpressionCompileError) as error:
        compile_expression(source, ())
    assert error.value.code == code


def test_limits_are_enforced():
    with pytest.raises(ExpressionCompileError, match="depth"):
        compile_expression("not " * 65 + "true", ())


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("false and missing", False),
        ("true or missing", True),
        ("null and true", None),
        ("null or true", True),
        ("coalesce(null, 7)", 7),
        ("null == 7", None),
    ],
)
def test_three_valued_logic_and_short_circuit(source: str, expected: object):
    inputs = (("missing", ref("Boolean")),) if "missing" in source else ()
    compiled = compile_expression(source, inputs)
    environment = values(missing=(ref("Boolean"), True)) if inputs else ComponentValues(())
    assert evaluate_expression(compiled, environment).value.value == expected


def test_decimal_is_exact_and_bankers_rounding_is_pinned():
    compiled = compile_expression("round(value, 2)", (("value", ref("Decimal")),))
    result = evaluate_expression(compiled, values(value=(ref("Decimal"), Decimal("2.345"))))
    assert result.value.value == Decimal("2.34")


def test_dates_and_fixed_durations():
    compiled = compile_expression('add_duration(date("2024-02-28"), duration(days: 1))', ())
    assert evaluate_expression(compiled, ComponentValues(())).value.value == date(2024, 2, 29)
    scaled = compile_expression("duration(hours: 3) * 2", ())
    assert evaluate_expression(scaled, ComponentValues(())).value.value == timedelta(hours=6)


def test_int64_overflow_is_deterministic():
    compiled = compile_expression("value + 1", (("value", ref("Integer")),))
    with pytest.raises(ExpressionEvaluationError) as error:
        evaluate_expression(compiled, values(value=(ref("Integer"), 2**63 - 1)))
    assert error.value.code == "integer_overflow"


def test_input_type_mismatch_fails_before_evaluation():
    compiled = compile_expression("value + 1", (("value", ref("Integer")),))
    with pytest.raises(ExpressionEvaluationError) as error:
        evaluate_expression(compiled, values(value=(ref("Decimal"), Decimal("1"))))
    assert error.value.code == "input_type"
