from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_provider_port_is_sdk_and_network_free() -> None:
    source = (ROOT / "market_data" / "providers.py").read_text()
    for name in (
        "import requests",
        "import httpx",
        "import tradier",
        "import finnhub",
        "import alpha_vantage",
        "os.environ",
    ):
        assert name not in source


def test_strategy_code_does_not_import_market_data_providers() -> None:
    for path in (ROOT / "strategies").rglob("*.py"):
        source = path.read_text()
        assert "market_data.providers" not in source
        assert "providers." not in source
