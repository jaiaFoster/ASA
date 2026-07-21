"""ASA-CORE-004: indicator-specific architecture validation.

Codifies the ticket's exact architecture_validation clauses beyond the
general AST-based boundary sweep in test_dependency_boundaries.py.
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


class TestIndicatorImportScope:
    """indicators/ imports only indicators, facts, reconciliation, domain."""

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "indicators").glob("*.py")))
    def test_only_allowed_roots(self, py_file):
        allowed = {"indicators", "facts", "reconciliation", "domain"} | STDLIB_ALLOWED
        imported = _imported_roots(py_file)
        assert imported <= allowed, (
            f"{py_file.name} imports outside {allowed}: {imported - allowed}"
        )

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "indicators").glob("*.py")))
    def test_no_observation_or_provider_import(self, py_file):
        """Narrower than the general pipeline rule (ADR-004 revision, ASA-CORE-004)."""
        imported = _imported_roots(py_file)
        assert "observation" not in imported
        assert "providers" not in imported

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "indicators").glob("*.py")))
    def test_no_strategy_ranking_or_guardrail_imports(self, py_file):
        imported = _imported_roots(py_file)
        assert not (imported & {"strategies", "ranking", "guardrails", "presentation"})

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "indicators").glob("*.py")))
    def test_no_infrastructure_dependencies(self, py_file):
        imported = _imported_roots(py_file)
        assert not (imported & FORBIDDEN_INFRASTRUCTURE_MODULES), (
            f"{py_file.name} imports infrastructure module(s): "
            f"{imported & FORBIDDEN_INFRASTRUCTURE_MODULES}"
        )


class TestNoIndicatorProhibitedTechniques:
    """Ticket's indicator_engine.prohibited: strategies, ranking, broker
    integration, provider access, randomness, external services."""

    def test_no_ml_libraries_imported(self):
        forbidden = {"sklearn", "torch", "tensorflow", "numpy", "scipy", "pandas"}
        for py_file in (REPO_ROOT / "indicators").glob("*.py"):
            imported = _imported_roots(py_file)
            assert not (imported & forbidden), f"{py_file.name} imports ML library"

    def test_no_random_or_uuid_usage(self):
        for py_file in (REPO_ROOT / "indicators").glob("*.py"):
            imported = _imported_roots(py_file)
            assert "random" not in imported
            assert "uuid" not in imported

    def test_no_network_calls(self):
        forbidden = {"socket", "http", "urllib", "requests", "aiohttp"}
        for py_file in (REPO_ROOT / "indicators").glob("*.py"):
            imported = _imported_roots(py_file)
            assert not (imported & forbidden)


class TestProhibitedIndicatorsNotImplemented:
    """RSI, MACD, Bollinger Bands, Options Greeks, and ML indicators must
    not exist anywhere in indicators/ (ticket's explicit prohibition)."""

    PROHIBITED_TERMS = ["rsi", "macd", "bollinger", "greeks", "delta", "gamma",
                        "theta", "vega", "implied_volatility"]

    def test_no_prohibited_indicator_names_registered(self):
        from indicators.registry import DEFAULT_REGISTRY
        registered = {t.lower() for t in DEFAULT_REGISTRY.registered_types()}
        for term in self.PROHIBITED_TERMS:
            assert not any(term in t for t in registered), (
                f"prohibited indicator term {term!r} found in registered types: {registered}"
            )

    def test_required_six_indicators_registered(self):
        from indicators.registry import DEFAULT_REGISTRY
        required = {
            "latest_price", "price_change_percent", "simple_moving_average",
            "exponential_moving_average", "rolling_high", "rolling_low",
        }
        assert required <= set(DEFAULT_REGISTRY.registered_types())

    def test_exactly_six_indicators_registered(self):
        from indicators.registry import DEFAULT_REGISTRY
        assert len(DEFAULT_REGISTRY.registered_types()) == 6
