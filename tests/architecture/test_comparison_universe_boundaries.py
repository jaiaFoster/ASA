"""SPRINT-013 S13-04C: architecture boundaries for the reusable
comparison-universe / sector-reference module.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).parents[2] / "strategy_runtime" / "comparison_universe.py"

_FORBIDDEN_ROOTS = {
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "requests",
    "httpx",
    "urllib",
    "alembic",
    "screening",
    "strategies",
    "asa",
}


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_comparison_universe_has_no_infrastructure_or_strategy_imports() -> None:
    tree = ast.parse(_MODULE.read_text())
    roots = _imported_roots(tree)
    violations = roots & _FORBIDDEN_ROOTS
    assert not violations, f"strategy_runtime/comparison_universe.py imports: {violations}"


def test_comparison_universe_only_imports_from_permitted_roots() -> None:
    permitted = {"__future__", "collections", "datetime", "domain"}
    tree = ast.parse(_MODULE.read_text())
    roots = _imported_roots(tree)
    violations = roots - permitted
    assert not violations, f"strategy_runtime/comparison_universe.py imports: {violations}"


def test_comparison_universe_has_no_strategy_identifier_conditionals() -> None:
    # A reusable module: no branching on a strategy's own name/id anywhere
    # in its source (Skew Momentum is the first consumer, not the owner).
    source = _MODULE.read_text()
    for needle in ("skew_momentum", "SKEW_MOMENTUM", "strategy_id", "strategy_name"):
        assert needle not in source, f"unexpected strategy-specific reference: {needle}"
