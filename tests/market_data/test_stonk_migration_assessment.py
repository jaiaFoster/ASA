from pathlib import Path


def test_stonk_market_data_assessment_classifies_required_legacy_paths() -> None:
    content = (
        Path(__file__).parents[2] / "docs/migration/stonk-market-data-assessment.md"
    ).read_text(encoding="utf-8")
    required = (
        "Tradier",
        "Finnhub",
        "Alpha Vantage",
        "MarketDataHub",
        "SQLite",
        "Option-chain behavior",
        "Earnings behavior",
        "### Migrate",
        "### Replace",
        "### Retire",
        "### Defer",
        "Follow-on work",
        "Do not migrate values",
        "Robinhood is prohibited",
    )
    assert all(item in content for item in required)
