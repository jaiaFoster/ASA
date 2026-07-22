from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_budget_manager_has_no_background_or_network_behavior() -> None:
    source = (ROOT / "market_data" / "budget.py").read_text()
    for token in ("threading", "asyncio", "sleep(", "requests", "httpx", "socket"):
        assert token not in source


def test_provider_fetch_requires_budget_authorization() -> None:
    source = (ROOT / "market_data" / "providers.py").read_text()
    assert "budget: RequestBudgetAuthorization" in source
