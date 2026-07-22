from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_only_market_data_config_reads_environment() -> None:
    config = (ROOT / "market_data" / "config.py").read_text()
    assert "os.environ" in config
    for path in (ROOT / "providers").rglob("*.py"):
        source = path.read_text()
        assert "os.getenv" not in source
        assert "os.environ" not in source


def test_market_data_config_contains_no_provider_sdk_imports() -> None:
    source = (ROOT / "market_data" / "config.py").read_text()
    for name in ("tradier", "finnhub", "alpha_vantage", "requests", "httpx"):
        assert f"import {name}" not in source
