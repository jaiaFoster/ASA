"""SPRINT-014 S14-PR-05A, Architect checkpoint: ninth review, item 4 --
"refactor strategies/earnings_calendar_evaluation.py into a truly
read-only evaluator ... it must no longer import or invoke
materialize_derived_fact(), compute_realized_volatility(),
compute_atm_iv_vs_realized_volatility(), or
compute_iv_term_structure_spread()". Proven directly against the module's
own source (both imports and call expressions), not merely by convention.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).resolve().parents[2] / "strategies" / "earnings_calendar_evaluation.py"

_FORBIDDEN_ANALYTICS_CALLS = (
    "materialize_derived_fact",
    "compute_realized_volatility",
    "compute_atm_iv_vs_realized_volatility",
    "compute_iv_term_structure_spread",
)


def _source() -> str:
    return _MODULE.read_text()


def _imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom | ast.Import):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _called_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def test_never_imports_a_forbidden_analytics_function() -> None:
    imported = _imported_names(ast.parse(_source()))
    found = imported & set(_FORBIDDEN_ANALYTICS_CALLS)
    assert not found, f"earnings_calendar_evaluation.py imports: {found}"


def test_never_calls_a_forbidden_analytics_function() -> None:
    called = _called_names(ast.parse(_source()))
    found = called & set(_FORBIDDEN_ANALYTICS_CALLS)
    assert not found, f"earnings_calendar_evaluation.py calls: {found}"


def test_only_permitted_import_roots() -> None:
    permitted = {
        "__future__",
        "analytics",
        "datetime",
        "decimal",
        "domain",
        "strategies",
    }
    tree = ast.parse(_source())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= permitted, (
        f"earnings_calendar_evaluation.py imports outside {permitted}: {roots - permitted}"
    )


def test_never_imports_market_data_screening_or_strategy_runtime() -> None:
    forbidden = {"market_data", "screening", "strategy_runtime", "facts"}
    tree = ast.parse(_source())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert not (roots & forbidden), (
        f"earnings_calendar_evaluation.py imports: {roots & forbidden}"
    )
