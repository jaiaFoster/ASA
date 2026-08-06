"""SPRINT-014 S14-PR-03: architecture boundaries for the subject-first
acquisition plan.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).parents[2] / "market_data" / "subject_plan.py"

_FORBIDDEN_ROOTS = {"screening", "strategies", "strategy_runtime", "asa"}


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_subject_plan_has_no_downstream_layer_imports() -> None:
    # market_data/ owns acquisition; it must never depend on screening,
    # strategies, strategy_runtime, or asa (canonical_flow, ASA-ARCH-007
    # section 18: "Strategy ... may import neither adapters nor SDKs" is
    # the inverse guarantee -- this asserts the acquisition side of the
    # same one-directional dependency rule).
    tree = ast.parse(_MODULE.read_text())
    roots = _imported_roots(tree)
    violations = roots & _FORBIDDEN_ROOTS
    assert not violations, f"market_data/subject_plan.py imports: {violations}"


def test_subject_plan_only_imports_from_permitted_roots() -> None:
    permitted = {"__future__", "market_data"}
    tree = ast.parse(_MODULE.read_text())
    roots = _imported_roots(tree)
    violations = roots - permitted
    assert not violations, f"market_data/subject_plan.py imports: {violations}"
