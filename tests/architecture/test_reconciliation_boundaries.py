"""ASA-CORE-003: reconciliation-specific architecture validation.

Codifies the ticket's explicit architecture_validation clauses beyond the
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

STDLIB_ALLOWED = {"__future__", "datetime", "hashlib", "collections", "typing", "decimal"}


def _imported_roots(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


class TestReconciliationImportScope:
    """reconciliation/ imports only domain, observation, reconciliation."""

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "reconciliation").glob("*.py")))
    def test_only_allowed_roots(self, py_file):
        allowed = {"domain", "observation", "reconciliation"} | STDLIB_ALLOWED
        imported = _imported_roots(py_file)
        assert imported <= allowed, (
            f"{py_file.name} imports outside {allowed}: {imported - allowed}"
        )

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "reconciliation").glob("*.py")))
    def test_no_strategy_or_ranking_imports(self, py_file):
        imported = _imported_roots(py_file)
        assert "strategies" not in imported
        assert "ranking" not in imported
        assert "guardrails" not in imported

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "reconciliation").glob("*.py")))
    def test_no_provider_package_import(self, py_file):
        """reconciliation may reference provider_id strings but not import providers/."""
        imported = _imported_roots(py_file)
        assert "providers" not in imported

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "reconciliation").glob("*.py")))
    def test_no_infrastructure_dependencies(self, py_file):
        imported = _imported_roots(py_file)
        assert not (imported & FORBIDDEN_INFRASTRUCTURE_MODULES), (
            f"{py_file.name} imports infrastructure module(s): "
            f"{imported & FORBIDDEN_INFRASTRUCTURE_MODULES}"
        )

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "reconciliation").glob("*.py")))
    def test_no_facts_import(self, py_file):
        """reconciliation must never depend on facts/ (facts depends on it, not vice versa)."""
        imported = _imported_roots(py_file)
        assert "facts" not in imported


class TestFactsImportScope:
    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "facts").glob("*.py")))
    def test_no_infrastructure_dependencies(self, py_file):
        imported = _imported_roots(py_file)
        assert not (imported & FORBIDDEN_INFRASTRUCTURE_MODULES), (
            f"{py_file.name} imports infrastructure module(s): "
            f"{imported & FORBIDDEN_INFRASTRUCTURE_MODULES}"
        )

    @pytest.mark.parametrize("py_file", sorted((REPO_ROOT / "facts").glob("*.py")))
    def test_no_strategy_ranking_or_provider_imports(self, py_file):
        imported = _imported_roots(py_file)
        assert not (imported & {"strategies", "ranking", "guardrails", "providers"})


class TestNoReconciliationProhibitedTechniques:
    """Ticket's reconciliation_engine.prohibited: ML, heuristics-as-libraries,
    randomness, provider weighting configuration, external APIs."""

    def test_no_ml_libraries_imported(self):
        forbidden = {"sklearn", "torch", "tensorflow", "numpy", "scipy", "pandas"}
        for py_file in (REPO_ROOT / "reconciliation").glob("*.py"):
            imported = _imported_roots(py_file)
            assert not (imported & forbidden), f"{py_file.name} imports ML library"

    def test_no_random_or_uuid_usage(self):
        for py_file in (REPO_ROOT / "reconciliation").glob("*.py"):
            imported = _imported_roots(py_file)
            assert "random" not in imported
            assert "uuid" not in imported

    def test_no_network_calls(self):
        forbidden = {"socket", "http", "urllib", "requests", "aiohttp"}
        for py_file in (REPO_ROOT / "reconciliation").glob("*.py"):
            imported = _imported_roots(py_file)
            assert not (imported & forbidden)

    def test_no_provider_priority_attribute_on_domain_provider(self):
        """Provider weighting is prohibited and has no field to weight by (ASA-CORE-001)."""
        content = (REPO_ROOT / "domain" / "provider.py").read_text()
        assert "priority" not in content.lower()
