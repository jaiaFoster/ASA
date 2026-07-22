from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_factory_has_no_environment_or_network_construction() -> None:
    source = (ROOT / "market_data" / "factory.py").read_text()
    for token in ("os.environ", "os.getenv", "requests", "httpx", "socket"):
        assert token not in source


def test_factory_has_no_module_level_provider_instances() -> None:
    source = (ROOT / "market_data" / "factory.py").read_text()
    assert "ProviderFactory(" not in source
    assert "MarketDataProvider()" not in source
