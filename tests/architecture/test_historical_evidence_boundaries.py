"""SPRINT-013 S13-04A: architecture boundaries for the new historical
evidence repository port.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MODULE = Path(__file__).parents[2] / "strategy_runtime" / "historical_evidence.py"

_FORBIDDEN_INFRASTRUCTURE_ROOTS = {
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "requests",
    "httpx",
    "urllib",
    "alembic",
}


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_historical_evidence_has_no_infrastructure_imports() -> None:
    tree = ast.parse(_MODULE.read_text())
    roots = _imported_roots(tree)
    violations = roots & _FORBIDDEN_INFRASTRUCTURE_ROOTS
    assert not violations, f"strategy_runtime/historical_evidence.py imports: {violations}"


def test_historical_evidence_only_imports_from_permitted_roots() -> None:
    # domain/market_data facts, strategy_runtime's own clock port -- never
    # asa, screening, or a concrete Postgres integration (this ticket's
    # own "persistence/integrations owns durable historical storage" rule
    # means the concrete adapter lives in asa/integrations, not here).
    permitted = {"__future__", "typing", "datetime", "domain", "market_data", "strategy_runtime"}
    tree = ast.parse(_MODULE.read_text())
    roots = _imported_roots(tree)
    violations = roots - permitted
    assert not violations, f"strategy_runtime/historical_evidence.py imports: {violations}"


def test_no_strategy_or_screening_file_imports_a_database_driver_for_history() -> None:
    # SPRINT-013 S13-04's own hard rule: no_private_strategy_database.
    # Confirms the current state (S13-04D, wiring Skew Momentum as a
    # consumer, has not landed yet) and will keep guarding it once it
    # does -- a strategy file may consume the repository *Protocol*
    # (already generic, already tested), never a concrete driver.
    root = Path(__file__).parents[2]
    forbidden_roots = {"sqlalchemy", "psycopg", "psycopg2", "alembic"}
    violations: list[str] = []
    for directory in (root / "strategies", root / "screening"):
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text())
            if _imported_roots(tree) & forbidden_roots:
                violations.append(str(path.relative_to(root)))
    assert not violations, f"strategy/screening files with a database driver import: {violations}"
