"""ASA-CORE-006: guardrail-specific architecture validation.

Codifies the ticket's exact allowed_imports/prohibited_imports lists
beyond the general AST-based boundary sweep in test_dependency_boundaries.py.
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
    "__future__",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "hashlib",
    "typing",
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


def _guardrail_files() -> list[Path]:
    return sorted((REPO_ROOT / "guardrails").glob("*.py"))


class TestGuardrailImportScope:
    """guardrails/ imports only guardrails, strategies, indicators, facts,
    reconciliation, domain."""

    @pytest.mark.parametrize("py_file", _guardrail_files())
    def test_only_allowed_roots(self, py_file):
        allowed = (
            {"guardrails", "strategies", "indicators", "facts", "reconciliation", "domain"}
            | STDLIB_ALLOWED
        )
        imported = _imported_roots(py_file)
        assert imported <= allowed, (
            f"{py_file.name} imports outside {allowed}: {imported - allowed}"
        )

    @pytest.mark.parametrize("py_file", _guardrail_files())
    def test_prohibited_imports_absent(self, py_file):
        """Ticket's explicit prohibited_imports list."""
        prohibited = {"providers", "observation", "ranking", "presentation"}
        imported = _imported_roots(py_file)
        assert not (imported & prohibited), (
            f"{py_file.name} imports prohibited module(s): {imported & prohibited}"
        )

    @pytest.mark.parametrize("py_file", _guardrail_files())
    def test_no_infrastructure_dependencies(self, py_file):
        imported = _imported_roots(py_file)
        assert not (imported & FORBIDDEN_INFRASTRUCTURE_MODULES), (
            f"{py_file.name} imports infrastructure module(s): "
            f"{imported & FORBIDDEN_INFRASTRUCTURE_MODULES}"
        )


class TestNoGuardrailProhibitedTechniques:
    """Ticket's prohibited list: ranking, execution, providers, observation,
    persistence, broker_access, randomness, machine_learning."""

    def test_no_ml_libraries_imported(self):
        forbidden = {"sklearn", "torch", "tensorflow", "numpy", "scipy", "pandas"}
        for py_file in _guardrail_files():
            imported = _imported_roots(py_file)
            assert not (imported & forbidden), f"{py_file.name} imports ML library"

    def test_no_random_or_uuid_usage(self):
        for py_file in _guardrail_files():
            imported = _imported_roots(py_file)
            assert "random" not in imported
            assert "uuid" not in imported

    def test_no_network_calls(self):
        forbidden = {"socket", "http", "urllib", "requests", "aiohttp"}
        for py_file in _guardrail_files():
            imported = _imported_roots(py_file)
            assert not (imported & forbidden)

    def test_no_persistence_modules(self):
        forbidden = {"sqlite3", "sqlalchemy", "psycopg2", "pickle", "shelve"}
        for py_file in _guardrail_files():
            imported = _imported_roots(py_file)
            assert not (imported & forbidden)

    def test_no_repository_module(self):
        """Persistence is explicitly out of scope — no guardrails/repository.py."""
        assert not (REPO_ROOT / "guardrails" / "repository.py").exists()


class TestRequiredGuardrailsRegistered:
    def test_five_required_guardrails_present(self):
        from guardrails.registry import DEFAULT_REGISTRY
        required = {
            "minimum_evidence_confidence", "maximum_capital_required",
            "maximum_loss", "allowed_time_horizon", "placeholder_metrics_rejection",
        }
        assert required <= set(DEFAULT_REGISTRY.registered_ids())

    def test_exactly_five_guardrails_registered(self):
        from guardrails.registry import DEFAULT_REGISTRY
        assert len(DEFAULT_REGISTRY.registered_ids()) == 5
