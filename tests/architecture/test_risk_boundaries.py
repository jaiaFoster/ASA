import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
FILES = sorted((ROOT / "risk").glob("*.py"))


def _roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            values.add(node.module.split(".")[0])
    return values


@pytest.mark.parametrize("path", FILES)
def test_risk_imports_only_domain_and_itself(path: Path) -> None:
    assert _roots(path) <= {"__future__", "dataclasses", "decimal", "domain", "hashlib", "risk"}


def test_risk_has_no_repository_provider_or_plugin_surface() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in FILES)
    for prohibited in ("providers", "repository", "sqlalchemy", "requests", "plugins"):
        assert prohibited not in combined
