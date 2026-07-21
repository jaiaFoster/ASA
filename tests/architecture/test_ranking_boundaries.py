"""ASA-CORE-007 Ranking Layer architecture validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_PROJECT_ROOTS = {
    "domain",
    "facts",
    "guardrails",
    "indicators",
    "ranking",
    "reconciliation",
    "strategies",
}
PROHIBITED_ROOTS = {
    "execution",
    "infrastructure",
    "observation",
    "presentation",
    "providers",
}
PROHIBITED_INFRASTRUCTURE = {
    "asyncio",
    "http",
    "multiprocessing",
    "psycopg2",
    "requests",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "threading",
    "urllib",
}
STDLIB_ALLOWED = {"__future__", "collections", "dataclasses", "decimal", "hashlib"}


def _files() -> list[Path]:
    return sorted((REPO_ROOT / "ranking").glob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", _files())
def test_ranking_imports_only_allowed_roots(path: Path) -> None:
    imported = _imports(path)
    allowed = ALLOWED_PROJECT_ROOTS | STDLIB_ALLOWED
    assert imported <= allowed, (
        f"{path.name} imports outside Ranking boundary: {imported - allowed}"
    )


@pytest.mark.parametrize("path", _files())
def test_ranking_has_no_prohibited_or_infrastructure_imports(path: Path) -> None:
    imported = _imports(path)
    assert not imported & PROHIBITED_ROOTS
    assert not imported & PROHIBITED_INFRASTRUCTURE


def test_required_ranking_modules_exist() -> None:
    assert {path.name for path in _files()} == {
        "__init__.py",
        "engine.py",
        "errors.py",
        "models.py",
        "registry.py",
        "scorers.py",
    }


def test_no_repository_or_persistence_module_exists() -> None:
    assert not (REPO_ROOT / "ranking" / "repository.py").exists()
    assert not (REPO_ROOT / "ranking" / "persistence.py").exists()


def test_no_randomness_ml_or_llm_imports() -> None:
    prohibited = {"openai", "random", "secrets", "sklearn", "tensorflow", "torch", "uuid"}
    for path in _files():
        assert not _imports(path) & prohibited


def test_ranking_does_not_mutate_opportunities() -> None:
    for path in _files():
        tree = ast.parse(path.read_text())
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        assert not any(node.func.id in {"setattr", "delattr"} for node in calls)
