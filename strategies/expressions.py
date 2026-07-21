"""Deterministic ASA Expression Language v1 (STRAT-007, ASA-ARCH-004)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import (
    Clamped,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    localcontext,
)
from typing import Any, TypeAlias, cast

from strategies.errors import ExpressionCompileError, ExpressionEvaluationError
from strategies.manifest import canonical_strategy_json
from strategies.type_system import (
    DEFAULT_TYPE_SYSTEM,
    TYPE_SYSTEM_VERSION,
    ComponentValues,
    StrategyTypeReference,
    TypedValue,
)

EXPRESSION_LANGUAGE_VERSION = "1.0.0"
EXPRESSION_IDENTITY_NAMESPACE = "asa.expression"
EXPRESSION_IDENTITY_VERSION = "v1"
FUNCTION_REGISTRY_VERSION = "1.0.0"
MAX_SOURCE_BYTES = 16_384
MAX_DEPTH = 64
MAX_NODES = 512
MAX_IDENTIFIERS = 128
MAX_FUNCTION_ARGUMENTS = 128
MAX_STEPS = 4_096
MAX_COLLECTION_LENGTH = 1_024
MAX_STRING_BYTES = 16_384
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1

DECIMAL_CONTEXT = Context(
    prec=34,
    rounding=ROUND_HALF_EVEN,
    Emin=-6143,
    Emax=6144,
    clamp=1,
)
for _signal in (InvalidOperation, DivisionByZero, Overflow):
    DECIMAL_CONTEXT.traps[_signal] = True
DECIMAL_CONTEXT.traps[Clamped] = False


@dataclass(frozen=True, slots=True)
class ExpressionLimits:
    source_bytes: int = MAX_SOURCE_BYTES
    depth: int = MAX_DEPTH
    nodes: int = MAX_NODES
    identifiers: int = MAX_IDENTIFIERS
    function_arguments: int = MAX_FUNCTION_ARGUMENTS
    steps: int = MAX_STEPS
    collection_length: int = MAX_COLLECTION_LENGTH
    string_bytes: int = MAX_STRING_BYTES


DEFAULT_EXPRESSION_LIMITS = ExpressionLimits()


ExpressionLiteral: TypeAlias = None | bool | int | Decimal | str | date | timedelta


@dataclass(frozen=True, slots=True)
class ExpressionNode:
    kind: str
    type_ref: StrategyTypeReference
    value: ExpressionLiteral
    children: tuple[ExpressionNode, ...] = field(default_factory=tuple)
    argument_names: tuple[str | None, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CompiledExpression:
    root: ExpressionNode
    result_type: StrategyTypeReference
    referenced_inputs: tuple[tuple[str, StrategyTypeReference], ...]
    limits: ExpressionLimits
    canonical_ast: bytes
    expression_id: str
    language_version: str = EXPRESSION_LANGUAGE_VERSION


@dataclass(frozen=True, slots=True)
class ExpressionTrace:
    expression_id: str
    input_names: tuple[str, ...]
    output_type: StrategyTypeReference | None
    output_identity: str | None
    evaluated_nodes: tuple[str, ...]
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ExpressionResult:
    value: TypedValue
    trace: ExpressionTrace


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    start: int


@dataclass(frozen=True, slots=True)
class _RawNode:
    kind: str
    value: object
    children: tuple[_RawNode, ...] = field(default_factory=tuple)
    argument_names: tuple[str | None, ...] = field(default_factory=tuple)


_TOKEN = re.compile(
    r"(?P<ws>[ \t\r\n]+)|(?P<decimal>(?:0|[1-9][0-9]*)\.[0-9]+(?:[eE][+-]?[0-9]+)?)|"
    r"(?P<integer>0|[1-9][0-9]*)|(?P<string>\"(?:[^\"\\]|\\[\"\\/bfnrt]|\\u[0-9A-Fa-f]{4})*\")|"
    r"(?P<op>==|!=|<=|>=|[+\-*/%<>() ,:])|(?P<identifier>[A-Za-z][A-Za-z0-9_]*)"
)


def _tokenize(source: str, limits: ExpressionLimits) -> tuple[_Token, ...]:
    if len(source.encode("utf-8")) > limits.source_bytes:
        raise ExpressionCompileError("source_too_long", "expression source exceeds limit")
    tokens: list[_Token] = []
    position = 0
    while position < len(source):
        match = _TOKEN.match(source, position)
        if match is None:
            raise ExpressionCompileError("syntax", f"unexpected character at {position}")
        kind = match.lastgroup
        if kind != "ws":
            text = match.group()
            if kind == "op":
                kind = text
            tokens.append(_Token(kind or "", text, position))
        position = match.end()
    tokens.append(_Token("eof", "", len(source)))
    return tuple(tokens)


class _Parser:
    def __init__(self, tokens: tuple[_Token, ...], limits: ExpressionLimits) -> None:
        self.tokens = tokens
        self.limits = limits
        self.index = 0
        self.nodes = 0

    def parse(self) -> _RawNode:
        node = self._or()
        if self._peek().kind != "eof":
            raise ExpressionCompileError("syntax", "unexpected trailing token")
        if _raw_depth(node) > self.limits.depth:
            raise ExpressionCompileError("limit_depth", "AST depth exceeds limit")
        return node

    def _node(
        self,
        kind: str,
        value: object,
        children: tuple[_RawNode, ...] = (),
        names: tuple[str | None, ...] = (),
    ) -> _RawNode:
        self.nodes += 1
        if self.nodes > self.limits.nodes:
            raise ExpressionCompileError("limit_nodes", "AST node count exceeds limit")
        return _RawNode(kind, value, children, names)

    def _peek(self) -> _Token:
        return self.tokens[self.index]

    def _take(self, kind: str | None = None) -> _Token:
        token = self._peek()
        if kind is not None and token.kind != kind:
            raise ExpressionCompileError("syntax", f"expected {kind}, found {token.text!r}")
        self.index += 1
        return token

    def _or(self) -> _RawNode:
        node = self._and()
        while self._peek().text == "or":
            self._take()
            node = self._node("binary", "or", (node, self._and()))
        return node

    def _and(self) -> _RawNode:
        node = self._comparison()
        while self._peek().text == "and":
            self._take()
            node = self._node("binary", "and", (node, self._comparison()))
        return node

    def _comparison(self) -> _RawNode:
        node = self._additive()
        if self._peek().kind in {"==", "!=", "<", "<=", ">", ">="}:
            operator = self._take().kind
            node = self._node("binary", operator, (node, self._additive()))
            if self._peek().kind in {"==", "!=", "<", "<=", ">", ">="}:
                raise ExpressionCompileError("syntax", "comparison chaining is forbidden")
        return node

    def _additive(self) -> _RawNode:
        node = self._multiplicative()
        while self._peek().kind in {"+", "-"}:
            operator = self._take().kind
            node = self._node("binary", operator, (node, self._multiplicative()))
        return node

    def _multiplicative(self) -> _RawNode:
        node = self._unary()
        while self._peek().kind in {"*", "/", "%"}:
            operator = self._take().kind
            node = self._node("binary", operator, (node, self._unary()))
        return node

    def _unary(self) -> _RawNode:
        if self._peek().kind in {"+", "-"} or self._peek().text == "not":
            operator = self._take().text
            return self._node("unary", operator, (self._unary(),))
        return self._primary()

    def _primary(self) -> _RawNode:
        token = self._peek()
        if token.kind == "integer":
            self._take()
            return self._node("literal", int(token.text))
        if token.kind == "decimal":
            self._take()
            with localcontext(DECIMAL_CONTEXT):
                value = Decimal(token.text)
            if not value.is_finite():
                raise ExpressionCompileError("decimal_invalid", "non-finite Decimal literal")
            return self._node("literal", value)
        if token.kind == "string":
            self._take()
            value = json.loads(token.text)
            if len(value.encode("utf-8")) > self.limits.string_bytes:
                raise ExpressionCompileError("string_limit", "string literal exceeds limit")
            return self._node("literal", value)
        if token.text in {"true", "false", "null"}:
            self._take()
            return self._node("literal", {"true": True, "false": False, "null": None}[token.text])
        if token.kind == "identifier":
            name = self._take().text
            if self._peek().kind == "(":
                return self._call(name)
            return self._node("input", name)
        if token.kind == "(":
            self._take()
            node = self._or()
            self._take(")")
            return node
        raise ExpressionCompileError("syntax", f"unexpected token {token.text!r}")

    def _call(self, name: str) -> _RawNode:
        self._take("(")
        children: list[_RawNode] = []
        names: list[str | None] = []
        if self._peek().kind != ")":
            while True:
                argument_name: str | None = None
                if self._peek().kind == "identifier" and self.tokens[self.index + 1].kind == ":":
                    argument_name = self._take().text
                    self._take(":")
                children.append(self._or())
                names.append(argument_name)
                if len(children) > self.limits.function_arguments:
                    raise ExpressionCompileError("arity", "too many function arguments")
                if self._peek().kind != ",":
                    break
                self._take(",")
        self._take(")")
        return self._node("call", name, tuple(children), tuple(names))


def _raw_depth(node: _RawNode) -> int:
    return 1 + max((_raw_depth(child) for child in node.children), default=0)


def _ref(name: str) -> StrategyTypeReference:
    return StrategyTypeReference(name, "1.0.0")


UNKNOWN = _ref("Unknown")


def compile_expression(
    source: str,
    input_types: tuple[tuple[str, StrategyTypeReference], ...],
    limits: ExpressionLimits = DEFAULT_EXPRESSION_LIMITS,
) -> CompiledExpression:
    raw = _Parser(_tokenize(source, limits), limits).parse()
    names = tuple(name for name, _ in input_types)
    if len(names) != len(set(names)):
        raise ExpressionCompileError("type", "duplicate input identifiers")
    if len(names) > limits.identifiers:
        raise ExpressionCompileError("limit_nodes", "referenced identifier limit exceeded")
    for _, type_ref in input_types:
        try:
            DEFAULT_TYPE_SYSTEM.resolve(type_ref)
        except ValueError as exc:
            raise ExpressionCompileError("type", "unknown or invalid input type") from exc
    environment = dict(input_types)
    referenced: set[str] = set()
    root = _compile_node(raw, environment, referenced)
    refs = tuple((name, environment[name]) for name in sorted(referenced))
    ast_data = _node_data(root)
    ast_bytes = canonical_strategy_json(ast_data)
    policy = {
        "language_version": EXPRESSION_LANGUAGE_VERSION,
        "function_registry_version": FUNCTION_REGISTRY_VERSION,
        "type_system_version": TYPE_SYSTEM_VERSION,
        "ast": ast_data,
        "inputs": [(name, _type_data(value)) for name, value in refs],
        "limits": limits.__dict__
        if hasattr(limits, "__dict__")
        else {field: getattr(limits, field) for field in limits.__slots__},
        "decimal": {"precision": 34, "rounding": "half_even", "emin": -6143, "emax": 6144},
    }
    expression_id = hashlib.sha256(
        canonical_strategy_json(
            {
                "identity_namespace": EXPRESSION_IDENTITY_NAMESPACE,
                "identity_version": EXPRESSION_IDENTITY_VERSION,
                **policy,
            }
        )
    ).hexdigest()
    return CompiledExpression(root, root.type_ref, refs, limits, ast_bytes, expression_id)


def _compile_node(
    raw: _RawNode,
    environment: dict[str, StrategyTypeReference],
    referenced: set[str],
) -> ExpressionNode:
    children = tuple(_compile_node(child, environment, referenced) for child in raw.children)
    if raw.kind == "literal":
        value = cast(ExpressionLiteral, raw.value)
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and not INT64_MIN <= value <= INT64_MAX
        ):
            raise ExpressionCompileError("overflow", "Integer literal exceeds int64")
        type_name = (
            "Boolean"
            if isinstance(value, bool)
            else "Integer"
            if isinstance(value, int)
            else "Decimal"
            if isinstance(value, Decimal)
            else "Text"
            if isinstance(value, str)
            else "Unknown"
        )
        return ExpressionNode(
            "literal", UNKNOWN if type_name == "Unknown" else _ref(type_name), value
        )
    if raw.kind == "input":
        name = str(raw.value)
        if name not in environment:
            raise ExpressionCompileError("unknown_identifier", f"unknown input {name}")
        referenced.add(name)
        return ExpressionNode("input", environment[name], name)
    if raw.kind == "unary":
        operand = children[0]
        operator = str(raw.value)
        if operator == "not" and _booleanish(operand.type_ref):
            result = operand.type_ref
        elif operator in {"+", "-"} and operand.type_ref.name in {"Integer", "Decimal"}:
            result = operand.type_ref
        else:
            raise ExpressionCompileError("type", f"invalid unary {operator}")
        return ExpressionNode("unary", result, operator, children)
    if raw.kind == "binary":
        return _compile_binary(str(raw.value), children)
    if raw.kind == "call":
        return _compile_call(str(raw.value), children, raw.argument_names)
    raise ExpressionCompileError("syntax", "unknown AST node")


def _compile_binary(operator: str, children: tuple[ExpressionNode, ...]) -> ExpressionNode:
    left, right = children
    if operator in {"and", "or"}:
        if not (_booleanish(left.type_ref) and _booleanish(right.type_ref)):
            raise ExpressionCompileError("type", "logical operands must be Boolean or Unknown")
        result = UNKNOWN if UNKNOWN in {left.type_ref, right.type_ref} else _ref("Boolean")
    elif operator in {"==", "!="}:
        if left.type_ref != right.type_ref and UNKNOWN not in {left.type_ref, right.type_ref}:
            raise ExpressionCompileError("type", "equality operands require exact equal types")
        result = UNKNOWN if UNKNOWN in {left.type_ref, right.type_ref} else _ref("Boolean")
    elif operator in {"<", "<=", ">", ">="}:
        if left.type_ref != right.type_ref or left.type_ref.name not in {
            "Integer",
            "Decimal",
            "Text",
            "Date",
            "Duration",
        }:
            raise ExpressionCompileError("type", "ordered operands require equal orderable types")
        result = _ref("Boolean")
    elif operator == "/":
        if left.type_ref.name != "Decimal" or right.type_ref != left.type_ref:
            raise ExpressionCompileError("type", "division requires two Decimals")
        result = left.type_ref
    elif (
        operator in {"+", "-", "*", "%"}
        and left.type_ref == right.type_ref
        and left.type_ref.name in {"Integer", "Decimal"}
    ):
        result = left.type_ref
    elif operator == "*" and (
        (left.type_ref.name == "Duration" and right.type_ref.name == "Integer")
        or (left.type_ref.name == "Integer" and right.type_ref.name == "Duration")
    ):
        result = _ref("Duration")
    elif (
        operator in {"+", "-"}
        and left.type_ref.name == "Date"
        and right.type_ref.name == "Duration"
    ):
        result = _ref("Date")
    elif operator == "-" and left.type_ref.name == right.type_ref.name == "Date":
        result = _ref("Duration")
    else:
        raise ExpressionCompileError("type", f"invalid operands for {operator}")
    return ExpressionNode("binary", result, operator, children)


def _compile_call(
    name: str, children: tuple[ExpressionNode, ...], names: tuple[str | None, ...]
) -> ExpressionNode:
    if (
        name == "date"
        and len(children) == 1
        and children[0].kind == "literal"
        and isinstance(children[0].value, str)
    ):
        try:
            value = date.fromisoformat(children[0].value)
        except ValueError as exc:
            raise ExpressionCompileError("syntax", "invalid Date literal") from exc
        return ExpressionNode("date_literal", _ref("Date"), value)
    if name == "duration":
        allowed = ("days", "hours", "minutes", "seconds")
        if (
            not children
            or any(item not in allowed for item in names)
            or len(set(names)) != len(names)
        ):
            raise ExpressionCompileError("syntax", "invalid Duration literal")
        values: dict[str, int] = {}
        for key, child in zip(names, children, strict=True):
            if key is None or child.kind != "literal" or not isinstance(child.value, int):
                raise ExpressionCompileError("type", "Duration units require Integer literals")
            values[key] = child.value
        return ExpressionNode("duration_literal", _ref("Duration"), timedelta(**values))
    if any(item is not None for item in names):
        raise ExpressionCompileError("syntax", "named arguments are allowed only for Duration")
    signatures: dict[str, tuple[int, int]] = {
        "is_null": (1, 1),
        "coalesce": (2, 2),
        "abs": (1, 1),
        "round": (1, 2),
        "floor": (1, 1),
        "ceil": (1, 1),
        "clamp": (3, 3),
        "minmax": (3, 3),
        "count": (1, 1),
        "sum": (1, 1),
        "min": (1, 1),
        "max": (1, 1),
        "average": (1, 1),
        "mean": (1, 1),
        "all": (1, 1),
        "any": (1, 1),
        "zscore": (2, 2),
        "add_duration": (2, 2),
        "subtract_duration": (2, 2),
    }
    if name not in signatures:
        raise ExpressionCompileError("unknown_function", f"unknown function {name}")
    low, high = signatures[name]
    if not low <= len(children) <= high:
        raise ExpressionCompileError("arity", f"invalid arity for {name}")
    result = _function_result_type(name, children)
    return ExpressionNode("call", result, name, children)


def _function_result_type(name: str, children: tuple[ExpressionNode, ...]) -> StrategyTypeReference:
    first = children[0].type_ref
    if name == "is_null":
        return _ref("Boolean")
    if name == "coalesce":
        if first != UNKNOWN and first != children[1].type_ref:
            raise ExpressionCompileError("type", "coalesce operands require equal types")
        return children[1].type_ref
    if name == "abs":
        _require(first.name in {"Integer", "Decimal"}, "abs requires numeric input")
        return first
    if name == "round":
        _require(first.name == "Decimal", "round requires Decimal input")
        if len(children) == 2:
            _require(children[1].type_ref.name == "Integer", "round digits require Integer")
        return first
    if name in {"floor", "ceil", "count"}:
        if name in {"floor", "ceil"}:
            _require(first.name == "Decimal", f"{name} requires Decimal input")
        else:
            _require(first.name == "List", "count requires List input")
        return _ref("Integer")
    if name in {"all", "any"}:
        _require(_list_argument(first, "Boolean"), f"{name} requires List[Boolean]")
        return _ref("Boolean")
    if name in {"clamp", "minmax"}:
        _require(
            all(child.type_ref == first for child in children)
            and first.name in {"Integer", "Decimal"},
            f"{name} requires three equal numeric types",
        )
        return _ref("Decimal") if name == "minmax" else first
    if name in {"sum", "min", "max", "average", "mean"}:
        _require(
            first.name == "List"
            and bool(first.arguments)
            and first.arguments[0].name in {"Integer", "Decimal"},
            f"{name} requires a numeric List",
        )
        if name in {"average", "mean"}:
            _require(first.arguments[0].name == "Decimal", f"{name} requires List[Decimal]")
            return _ref("Decimal")
        return first.arguments[0]
    if name == "zscore":
        _require(
            first.name == "Decimal" and _list_argument(children[1].type_ref, "Decimal"),
            "zscore requires Decimal and List[Decimal]",
        )
        return _ref("Decimal")
    if name in {"add_duration", "subtract_duration"}:
        _require(
            first.name == "Date" and children[1].type_ref.name == "Duration",
            f"{name} requires Date and Duration",
        )
        return _ref("Date")
    raise ExpressionCompileError("unknown_function", f"unknown function {name}")


def _list_argument(value: StrategyTypeReference, name: str) -> bool:
    return value.name == "List" and bool(value.arguments) and value.arguments[0].name == name


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExpressionCompileError("type", message)


def _booleanish(value: StrategyTypeReference) -> bool:
    return bool(value.name == "Boolean" or value == UNKNOWN)


def _type_data(value: StrategyTypeReference) -> dict[str, object]:
    return {
        "name": value.name,
        "version": value.version,
        "arguments": [_type_data(item) for item in value.arguments],
    }


def _literal_data(value: ExpressionLiteral) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    return value


def _node_data(node: ExpressionNode) -> dict[str, object]:
    return {
        "kind": node.kind,
        "type": _type_data(node.type_ref),
        "value": _literal_data(node.value),
        "children": [_node_data(item) for item in node.children],
        "argument_names": list(node.argument_names),
    }


def evaluate_expression(
    compiled: CompiledExpression, environment: ComponentValues
) -> ExpressionResult:
    supplied = {name: value for name, value in environment.entries}
    for name, expected in compiled.referenced_inputs:
        if name not in supplied:
            raise ExpressionEvaluationError("missing_input", f"missing input {name}")
        if supplied[name].type_ref != expected:
            raise ExpressionEvaluationError("input_type", f"input type mismatch for {name}")
        try:
            DEFAULT_TYPE_SYSTEM.validate_value(supplied[name])
        except ValueError as exc:
            raise ExpressionEvaluationError(
                "input_type", f"invalid input value for {name}"
            ) from exc
    trace: list[str] = []
    steps = [0]
    value = _evaluate(compiled.root, supplied, trace, steps, compiled.limits)
    typed = TypedValue(compiled.result_type, value)
    output_identity = hashlib.sha256(
        canonical_strategy_json(_literal_data(cast(ExpressionLiteral, value)))
    ).hexdigest()
    return ExpressionResult(
        typed,
        ExpressionTrace(
            compiled.expression_id,
            tuple(name for name, _ in compiled.referenced_inputs),
            compiled.result_type,
            output_identity,
            tuple(trace),
        ),
    )


def _evaluate(
    node: ExpressionNode,
    env: dict[str, TypedValue],
    trace: list[str],
    steps: list[int],
    limits: ExpressionLimits,
) -> Any:
    steps[0] += 1
    if steps[0] > limits.steps:
        raise ExpressionEvaluationError("step_limit", "evaluation step limit exceeded")
    trace.append(hashlib.sha256(canonical_strategy_json(_node_data(node))).hexdigest())
    if node.kind in {"literal", "date_literal", "duration_literal"}:
        return node.value
    if node.kind == "input":
        return env[str(node.value)].value
    if node.kind == "unary":
        value = _evaluate(node.children[0], env, trace, steps, limits)
        if value is None:
            return None
        if node.value == "not":
            return not value
        if node.value == "+":
            return value
        return _checked_numeric(-cast(int | Decimal | timedelta, value))
    if node.kind == "binary":
        left = _evaluate(node.children[0], env, trace, steps, limits)
        operator = str(node.value)
        if operator == "and" and left is False:
            return False
        if operator == "or" and left is True:
            return True
        right = _evaluate(node.children[1], env, trace, steps, limits)
        if operator == "and":
            return (
                False if right is False else None if left is None or right is None else bool(right)
            )
        if operator == "or":
            return True if right is True else None if left is None or right is None else bool(right)
        if left is None or right is None:
            return None
        if operator == "==":
            return left == right
        if operator == "!=":
            return left != right
        try:
            with localcontext(DECIMAL_CONTEXT):
                result = _binary_value(operator, left, right)
        except (ArithmeticError, OverflowError) as exc:
            code = "divide_by_zero" if right == 0 and operator in {"/", "%"} else "integer_overflow"
            raise ExpressionEvaluationError(code, f"operator {operator} failed") from exc
        return _checked_numeric(result)
    args = [_evaluate(child, env, trace, steps, limits) for child in node.children]
    return _call(str(node.value), args)


def _checked_numeric(value: object) -> object:
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and not INT64_MIN <= value <= INT64_MAX
    ):
        raise ExpressionEvaluationError("integer_overflow", "int64 overflow")
    if isinstance(value, Decimal) and not value.is_finite():
        raise ExpressionEvaluationError("decimal_invalid", "non-finite Decimal")
    return value


def _binary_value(operator: str, left: object, right: object) -> object:
    if operator in {"<", "<=", ">", ">="}:
        comparable_left = cast(Any, left)
        comparable_right = cast(Any, right)
        if operator == "<":
            return comparable_left < comparable_right
        if operator == "<=":
            return comparable_left <= comparable_right
        if operator == ">":
            return comparable_left > comparable_right
        return comparable_left >= comparable_right
    if isinstance(left, timedelta) and isinstance(right, int):
        return left * right
    if isinstance(left, int) and isinstance(right, timedelta):
        return right * left
    numeric_left = cast(int | Decimal, left)
    numeric_right = cast(int | Decimal, right)
    if operator == "+":
        return numeric_left + numeric_right
    if operator == "-":
        return numeric_left - numeric_right
    if operator == "*":
        return numeric_left * numeric_right
    if operator == "/":
        return cast(Decimal, numeric_left) / cast(Decimal, numeric_right)
    return numeric_left % numeric_right


def _call(name: str, args: list[object]) -> object:
    if name == "is_null":
        return args[0] is None
    if name == "coalesce":
        return args[1] if args[0] is None else args[0]
    if any(value is None for value in args):
        return None
    if name == "abs":
        return _checked_numeric(abs(cast(int | Decimal, args[0])))
    if name == "floor":
        return int(cast(Decimal, args[0]).to_integral_value(rounding=ROUND_FLOOR))
    if name == "ceil":
        return int(cast(Decimal, args[0]).to_integral_value(rounding=ROUND_CEILING))
    if name == "round":
        digits = cast(int, args[1]) if len(args) == 2 else 0
        if not -34 <= digits <= 34:
            raise ExpressionEvaluationError("invalid_conversion", "round digits out of range")
        return cast(Decimal, args[0]).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_EVEN)
    if name == "clamp":
        value, lower, upper = cast(tuple[Decimal, Decimal, Decimal], tuple(args))
        if lower > upper:
            raise ExpressionEvaluationError("invalid_bounds", "reversed clamp bounds")
        return min(max(value, lower), upper)
    if name == "minmax":
        value, lower, upper = cast(tuple[Decimal, Decimal, Decimal], tuple(args))
        if lower >= upper:
            raise ExpressionEvaluationError("invalid_bounds", "invalid minmax bounds")
        return (value - lower) / (upper - lower)
    if name == "count":
        return len(cast(tuple[object, ...], args[0]))
    if name in {"sum", "min", "max", "average", "mean", "all", "any"}:
        values = cast(tuple[object, ...], args[0])
        if len(values) > MAX_COLLECTION_LENGTH:
            raise ExpressionEvaluationError("collection_limit", "collection too large")
        if name == "sum":
            if values and isinstance(values[0], Decimal):
                return sum(cast(tuple[Decimal, ...], values), Decimal(0))
            return sum(cast(tuple[int, ...], values), 0)
        if name in {"min", "max", "average", "mean"} and not values:
            raise ExpressionEvaluationError("empty_aggregation", "empty collection")
        if name == "min":
            return min(cast(tuple[int | Decimal | str | date | timedelta, ...], values))
        if name == "max":
            return max(cast(tuple[int | Decimal | str | date | timedelta, ...], values))
        if name in {"average", "mean"}:
            return sum(cast(tuple[Decimal, ...], values), Decimal(0)) / Decimal(len(values))
        if name == "all":
            return _three_all(values)
        return _three_any(values)
    if name in {"add_duration", "subtract_duration"}:
        duration = cast(timedelta, args[1])
        if duration.total_seconds() % 86400:
            raise ExpressionEvaluationError("duration_range", "duration must be whole days")
        date_value = cast(date, args[0])
        return date_value + duration if name == "add_duration" else date_value - duration
    if name == "zscore":
        value = cast(Decimal, args[0])
        values = cast(tuple[Decimal, ...], args[1])
        if not values:
            raise ExpressionEvaluationError("empty_aggregation", "empty collection")
        mean = sum(values, Decimal(0)) / Decimal(len(values))
        variance = sum(((item - mean) ** 2 for item in values), Decimal(0)) / Decimal(len(values))
        deviation = variance.sqrt(context=DECIMAL_CONTEXT)
        if deviation == 0:
            raise ExpressionEvaluationError("divide_by_zero", "zero zscore deviation")
        return (value - mean) / deviation
    raise ExpressionEvaluationError("invalid_conversion", f"unimplemented function {name}")


def _three_all(values: tuple[object, ...]) -> object:
    if False in values:
        return False
    return None if None in values else True


def _three_any(values: tuple[object, ...]) -> object:
    if True in values:
        return True
    return None if None in values else False
