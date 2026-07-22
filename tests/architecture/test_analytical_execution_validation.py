import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGES = ("position_proposals", "portfolio", "risk", "execution_planning", "simulation")


def test_analytical_execution_source_has_no_live_capability() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for package in PACKAGES
        for path in (ROOT / package).glob("*.py")
    ).lower()
    for prohibited in (
        "submit_order", "cancel_order", "modify_order", "place_order",
        "broker_auth", "robin_stocks", "requests.", "httpx.", "sqlalchemy",
    ):
        assert prohibited not in source


def test_cross_package_import_matrix_matches_arch_006() -> None:
    allowed = {
        "position_proposals": {"domain", "position_proposals", "ranking"},
        "portfolio": {"domain", "portfolio"},
        "risk": {"domain", "risk"},
        "execution_planning": {"domain", "execution_planning"},
        "simulation": {"domain", "portfolio", "simulation"},
    }
    standard = {
        "__future__", "collections", "dataclasses", "datetime", "decimal", "enum", "hashlib",
    }
    for package in PACKAGES:
        for path in (ROOT / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            roots: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    roots.add(node.module.split(".")[0])
            assert roots <= allowed[package] | standard, (path, roots - allowed[package] - standard)
