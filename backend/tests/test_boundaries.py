import ast
from pathlib import Path


def test_provider_sdk_imports_are_confined_to_integrations() -> None:
    source_root = Path(__file__).parents[1] / "src" / "asa"
    forbidden_roots = {"finnhub", "tradier", "robin_stocks", "alpha_vantage"}
    violations: list[str] = []
    for path in source_root.rglob("*.py"):
        if "integrations" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(name.split(".")[0] in forbidden_roots for name in names):
                violations.append(str(path.relative_to(source_root)))
    assert not violations, f"provider imports outside integrations: {violations}"


def test_forbidden_legacy_technologies_are_absent() -> None:
    root = Path(__file__).parents[2]
    inspected = [root / "backend" / "src", root / "frontend" / "src"]
    forbidden = ("flask", "sqlite", "threading", "robinhood", "strategy")
    matches = []
    for directory in inspected:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx"}:
                lowered = path.read_text().lower()
                matches.extend(f"{path}:{term}" for term in forbidden if term in lowered)
    assert not matches


def test_exactly_one_build_application_composition_root_exists() -> None:
    source_root = Path(__file__).parents[1] / "src" / "asa"
    definitions = []
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        definitions.extend(
            f"{path}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "build_application"
        )
    assert len(definitions) == 1, definitions


def test_broker_provider_contract_is_read_only() -> None:
    from asa.application.ports.brokers import BrokerPortfolioProvider

    operations = {
        name
        for name, value in vars(BrokerPortfolioProvider).items()
        if callable(value) and not name.startswith("_")
    }
    assert operations == {"fetch_accounts", "fetch_positions"}
