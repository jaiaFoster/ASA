"""ASA-CORE-005: strategy-specific architecture validation.

Codifies the ticket's exact architecture_validation permitted/prohibited
import lists beyond the general AST-based boundary sweep in
test_dependency_boundaries.py.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_INFRASTRUCTURE_MODULES = {
    "sqlite3", "psycopg2", "sqlalchemy", "asyncio", "threading",
    "multiprocessing", "socket", "http", "urllib", "requests",
    "random", "secrets",
}

STDLIB_ALLOWED = {"__future__", "datetime", "hashlib", "decimal", "typing", "dataclasses"}


def _imported_roots(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _strategy_files() -> list[Path]:
    return sorted((REPO_ROOT / "strategies").glob("*.py"))


class TestStrategyImportScope:
    """strategies/ imports only strategies, indicators, facts, reconciliation, domain."""

    @pytest.mark.parametrize("py_file", _strategy_files())
    def test_only_permitted_roots(self, py_file):
        permitted = {"strategies", "indicators", "facts", "reconciliation", "domain"} | STDLIB_ALLOWED
        imported = _imported_roots(py_file)
        assert imported <= permitted, (
            f"{py_file.name} imports outside {permitted}: {imported - permitted}"
        )

    @pytest.mark.parametrize("py_file", _strategy_files())
    def test_prohibited_imports_absent(self, py_file):
        """Ticket's explicit prohibited_imports list."""
        prohibited = {"observation", "providers", "ranking", "guardrails", "presentation"}
        imported = _imported_roots(py_file)
        assert not (imported & prohibited), (
            f"{py_file.name} imports prohibited module(s): {imported & prohibited}"
        )

    @pytest.mark.parametrize("py_file", _strategy_files())
    def test_no_infrastructure_dependencies(self, py_file):
        imported = _imported_roots(py_file)
        assert not (imported & FORBIDDEN_INFRASTRUCTURE_MODULES), (
            f"{py_file.name} imports infrastructure module(s): "
            f"{imported & FORBIDDEN_INFRASTRUCTURE_MODULES}"
        )


class TestNoStrategyProhibitedTechniques:
    """Ticket's strategy_engine.prohibited: ranking, broker access, provider
    access, APIs, persistence, risk management, capital allocation,
    randomness, ML."""

    def test_no_ml_libraries_imported(self):
        forbidden = {"sklearn", "torch", "tensorflow", "numpy", "scipy", "pandas"}
        for py_file in _strategy_files():
            imported = _imported_roots(py_file)
            assert not (imported & forbidden), f"{py_file.name} imports ML library"

    def test_no_random_or_uuid_usage(self):
        for py_file in _strategy_files():
            imported = _imported_roots(py_file)
            assert "random" not in imported
            assert "uuid" not in imported

    def test_no_network_calls(self):
        forbidden = {"socket", "http", "urllib", "requests", "aiohttp"}
        for py_file in _strategy_files():
            imported = _imported_roots(py_file)
            assert not (imported & forbidden)

    def test_no_persistence_modules(self):
        forbidden = {"sqlite3", "sqlalchemy", "psycopg2", "pickle", "shelve"}
        for py_file in _strategy_files():
            imported = _imported_roots(py_file)
            assert not (imported & forbidden)


class TestRequiredStrategiesRegistered:
    def test_three_required_strategies_present(self):
        from strategies.registry import DEFAULT_REGISTRY
        required = {"moving_average_crossover", "breakout", "momentum"}
        assert required <= set(DEFAULT_REGISTRY.registered_ids())

    def test_exactly_three_strategies_registered(self):
        from strategies.registry import DEFAULT_REGISTRY
        assert len(DEFAULT_REGISTRY.registered_ids()) == 3

    def test_no_prohibited_strategy_names(self):
        from strategies.registry import DEFAULT_REGISTRY
        prohibited_terms = ["ml", "option", "volatility_forecast", "optimi", "adaptive"]
        registered = {s.lower() for s in DEFAULT_REGISTRY.registered_ids()}
        for term in prohibited_terms:
            assert not any(term in s for s in registered), (
                f"prohibited strategy term {term!r} found in registered ids: {registered}"
            )
