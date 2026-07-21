"""ASA-CORE-008 Position Proposal Layer architecture validation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_ROOTS = {
    "__future__",
    "dataclasses",
    "decimal",
    "domain",
    "hashlib",
    "position_proposals",
    "ranking",
}
PROHIBITED_ROOTS = {
    "backend",
    "brokers",
    "execution",
    "facts",
    "infrastructure",
    "observation",
    "providers",
    "sqlalchemy",
}


def _files() -> list[Path]:
    return sorted((REPO_ROOT / "position_proposals").glob("*.py"))


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
def test_position_proposals_import_only_ranking_and_domain(path: Path) -> None:
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
    assert not (REPO_ROOT / "position_proposals" / "repository.py").exists()
    assert not (REPO_ROOT / "position_proposals" / "persistence.py").exists()


def test_engine_has_no_portfolio_or_operational_input_imports() -> None:
    tree = ast.parse((REPO_ROOT / "position_proposals" / "engine.py").read_text())
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert not imported_names & {"Holding", "PortfolioSnapshot", "PortfolioDecision"}


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
