from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_registry_is_provider_neutral_and_has_no_runtime_registration() -> None:
    source = (ROOT / "market_data" / "registry.py").read_text()
    for token in ("tradier", "finnhub", "alpha_vantage", "importlib", "entry_points"):
        assert token not in source
    assert "def register(" not in source


def test_strategies_do_not_import_registries() -> None:
    for path in (ROOT / "strategies").rglob("*.py"):
        assert "market_data.registry" not in path.read_text()
