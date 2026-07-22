import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
FILES = sorted((ROOT / "simulation").glob("*.py"))


def _roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", FILES)
def test_simulation_imports_only_domain_and_itself(path: Path) -> None:
    assert _roots(path) <= {
        "__future__", "dataclasses", "datetime", "decimal", "domain", "enum",
        "hashlib", "portfolio", "simulation",
    }


def test_no_operational_capability_is_reachable() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in FILES)
    for value in ("requests", "providers", "broker", "authenticate", "submit_order", "sqlalchemy"):
        assert value not in source.lower()
