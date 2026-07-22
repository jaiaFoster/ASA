from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_market_data_domain_has_no_provider_sdk_or_infrastructure_imports() -> None:
    source = (ROOT / "domain" / "market_data.py").read_text()
    prohibited = (
        "requests",
        "httpx",
        "tradier",
        "finnhub",
        "alpha_vantage",
        "sqlalchemy",
        "psycopg",
        "os.getenv",
    )
    for name in prohibited:
        assert name not in source


def test_market_data_reuses_financial_option_and_earnings_contracts() -> None:
    source = (ROOT / "domain" / "market_data.py").read_text()
    assert "from domain.financial import" in source
    assert "class OptionContract" not in source
    assert "class OptionChain" not in source
    assert "class EarningsEvent" not in source
