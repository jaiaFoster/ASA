"""ASA-CORE-009 Portfolio Layer architecture validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_ROOTS = {
    "__future__",
    "collections",
    "dataclasses",
    "decimal",
    "domain",
    "hashlib",
    "portfolio",
}
PROHIBITED_ROOTS = {
    "backend",
    "brokers",
    "execution",
    "infrastructure",
    "observation",
    "position_proposals",
    "providers",
    "ranking",
    "sqlalchemy",
}


def _files() -> list[Path]:
    return sorted((REPO_ROOT / "portfolio").glob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", _files())
def test_portfolio_imports_only_domain_and_portfolio(path: Path) -> None:
    imported = _imports(path)
    assert imported <= ALLOWED_ROOTS
    assert not imported & PROHIBITED_ROOTS


def test_required_modules_exist_and_no_repository_exists() -> None:
    assert {path.name for path in _files()} == {
        "__init__.py",
        "engine.py",
        "errors.py",
        "models.py",
    }
    assert not (REPO_ROOT / "portfolio" / "repository.py").exists()
    assert not (REPO_ROOT / "portfolio" / "persistence.py").exists()


def test_no_randomness_networking_or_side_effect_imports() -> None:
    prohibited = {
        "asyncio",
        "httpx",
        "openai",
        "random",
        "requests",
        "secrets",
        "socket",
        "threading",
        "urllib",
        "uuid",
    }
    for path in _files():
        assert not _imports(path) & prohibited
