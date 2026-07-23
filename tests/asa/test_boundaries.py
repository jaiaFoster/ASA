import ast
from pathlib import Path


def test_provider_sdk_imports_are_confined_to_integrations() -> None:
    source_root = Path(__file__).parents[2] / "asa"
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
    # "strategy" was dropped from this list under SPRINT-009/EPIC-9: this
    # check predates strategy_runtime (Founder-approved package name,
    # GOV-011/docs/sprints/SPRINT-009.yaml) and its original intent -- no
    # literal port of the legacy Stonk predecessor's per-strategy OOP
    # service classes into asa/ -- was never meant to block asa/'s own
    # Postgres integration for the new, generalized runtime asa/
    # integrations/universal_screening_postgres.py imports strategy_runtime
    # by design, matching asa/integrations/screening_postgres.py's own
    # established "asa/ owns the database driver" role for screening/.
    root = Path(__file__).parents[2]
    inspected = [root / "asa", root / "frontend" / "src"]
    forbidden = ("flask", "sqlite", "threading")
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
    source_root = Path(__file__).parents[2] / "asa"
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


def test_robinhood_adapter_calls_only_approved_read_sdk_operations() -> None:
    adapter = (
        Path(__file__).parents[2] / "asa" / "integrations" / "providers" / "robinhood.py"
    )
    tree = ast.parse(adapter.read_text())
    references = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "robinhood"
    }
    assert references == {
        "login",
        "load_account_profile",
        "get_open_stock_positions",
        "get_open_option_positions",
        "get_instrument_by_url",
        "get_option_instrument_data_by_id",
    }
