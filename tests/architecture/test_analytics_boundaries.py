"""ANALYTICS-001: derived analytics framework architecture validation.

Mirrors test_screening_boundaries.py's pattern: an explicit permitted-import
allowlist plus prohibited-import and no-network/no-persistence/no-provider-
access sweeps. analytics/ is meant to be more foundational than screening/
-- it must not depend on screening, strategies, market_data, or providers,
so any future consumer (screening, a future strategy, or something else
entirely) can reuse it without pulling in an unrelated bounded context.
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

STDLIB_ALLOWED = {
    "__future__", "abc", "collections", "dataclasses", "datetime", "decimal", "enum", "hashlib",
    "json", "re", "typing",
}


def _imported_roots(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _analytics_files() -> list[Path]:
    return sorted((REPO_ROOT / "analytics").glob("*.py"))


class TestAnalyticsImportScope:
    """analytics/ imports only analytics, domain, and stdlib -- never
    screening, strategies, market_data, providers, or any bounded-context
    implementation module. This package must stay reusable by anything.
    """

    @pytest.mark.parametrize("py_file", _analytics_files())
    def test_only_permitted_roots(self, py_file: Path) -> None:
        permitted = {"analytics", "domain"} | STDLIB_ALLOWED
        imported = _imported_roots(py_file)
        assert imported <= permitted, (
            f"{py_file.name} imports outside {permitted}: {imported - permitted}"
        )

    @pytest.mark.parametrize("py_file", _analytics_files())
    def test_prohibited_imports_absent(self, py_file: Path) -> None:
        prohibited = {
            "market_data", "providers", "observation", "screening", "strategies",
            "ranking", "guardrails", "presentation", "simulation", "execution_planning",
        }
        imported = _imported_roots(py_file)
        assert not (imported & prohibited), (
            f"{py_file.name} imports prohibited module(s): {imported & prohibited}"
        )

    @pytest.mark.parametrize("py_file", _analytics_files())
    def test_no_infrastructure_dependencies(self, py_file: Path) -> None:
        imported = _imported_roots(py_file)
        assert not (imported & FORBIDDEN_INFRASTRUCTURE_MODULES), (
            f"{py_file.name} imports infrastructure module(s): "
            f"{imported & FORBIDDEN_INFRASTRUCTURE_MODULES}"
        )

    @pytest.mark.parametrize("py_file", _analytics_files())
    def test_no_network_or_persistence(self, py_file: Path) -> None:
        forbidden = {
            "socket", "http", "urllib", "requests", "aiohttp",
            "sqlite3", "sqlalchemy", "psycopg2", "pickle", "shelve",
        }
        imported = _imported_roots(py_file)
        assert not (imported & forbidden)

    @pytest.mark.parametrize("py_file", _analytics_files())
    def test_no_random_or_ml_libraries(self, py_file: Path) -> None:
        forbidden = {"random", "sklearn", "torch", "tensorflow", "numpy", "scipy", "pandas"}
        imported = _imported_roots(py_file)
        assert not (imported & forbidden)


class TestAnalyticsRegistryIsClosedAndExplicit:
    def test_registry_requires_explicit_construction(self) -> None:
        from analytics.registry import AnalyticsRegistry

        assert AnalyticsRegistry().registered_ids() == ()

    def test_no_dynamic_discovery_helpers_exposed(self) -> None:
        import analytics

        forbidden_names = {"discover", "autoregister", "scan_plugins", "load_plugins"}
        assert not (forbidden_names & set(dir(analytics)))
