from datetime import UTC, datetime
from pathlib import Path

import pytest

from asa.integrations.providers import robinhood as robinhood_module
from asa.integrations.providers.robinhood import (
    RobinhoodPortfolioProvider,
    RobinhoodProviderError,
    RobinStocksReadClient,
)


class FakeRobinhoodReadClient:
    def __init__(self) -> None:
        self.authenticated = 0

    def authenticate(self) -> None:
        self.authenticated += 1

    def accounts(self) -> list[dict[str, object]]:
        return [
            {
                "account_number": "RH-ACCOUNT-1",
                "type": "individual",
                "cash": "1250.50",
                "cash_available_for_withdrawal": "1000.25",
                "buying_power": "2500.75",
                "updated_at": "2026-07-19T11:00:00Z",
            }
        ]

    def portfolio(self, account_number: str) -> dict[str, object]:
        assert account_number == "RH-ACCOUNT-1"
        return {"equity": "50250.75"}

    def equity_positions(self) -> list[dict[str, object]]:
        return [
            {
                "account_number": "RH-ACCOUNT-1",
                "instrument": "https://api.robinhood.test/instruments/aapl/",
                "quantity": "3.5",
                "average_buy_price": "175.25",
                "updated_at": "2026-07-19T11:01:00Z",
            }
        ]

    def option_positions(self) -> list[dict[str, object]]:
        return [
            {
                "account_number": "RH-ACCOUNT-1",
                "option_id": "option-1",
                "quantity": "1",
                "type": "long",
                "average_price": "420.00",
                "updated_at": "2026-07-19T11:02:00Z",
            }
        ]

    def stock_instrument(self, url: str) -> dict[str, object]:
        assert url.endswith("/aapl/")
        return {"symbol": "AAPL"}

    def option_instrument(self, option_id: str) -> dict[str, object]:
        assert option_id == "option-1"
        return {
            "id": "option-1",
            "symbol": "AAPL260918C00200000",
            "chain_symbol": "AAPL",
            "type": "call",
            "strike_price": "200.00",
            "expiration_date": "2026-09-18",
        }


def test_robin_stocks_client_persists_and_reuses_trusted_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, object]] = []

    def login(**kwargs: object) -> dict[str, str]:
        calls.append(kwargs)
        session_file = tmp_path / "robinhoodasa_trusted_session.pickle"
        if not session_file.exists():
            session_file.write_bytes(b"opaque-test-session")
        monkeypatch.setattr(robinhood_module.robinhood_helper, "LOGGED_IN", True)
        return {"detail": "trusted session available"}

    monkeypatch.setattr(robinhood_module.robinhood, "login", login)
    first = RobinStocksReadClient("user", "password", None, (), str(tmp_path))
    second = RobinStocksReadClient("user", "password", None, (), str(tmp_path))

    first.authenticate()
    second.authenticate()

    assert len(calls) == 2
    assert all(call["store_session"] is True for call in calls)
    assert all(call["pickle_path"] == str(tmp_path) for call in calls)
    assert all(call["pickle_name"] == "asa_trusted_session" for call in calls)
    assert (tmp_path.stat().st_mode & 0o777) == 0o700
    assert ((tmp_path / "robinhoodasa_trusted_session.pickle").stat().st_mode & 0o777) == 0o600


@pytest.mark.parametrize("expired_session_exists", [False, True])
def test_robin_stocks_client_reports_manual_approval_without_disclosure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, expired_session_exists: bool
) -> None:
    if expired_session_exists:
        (tmp_path / "robinhoodasa_trusted_session.pickle").write_bytes(b"expired")
    monkeypatch.setattr(robinhood_module.robinhood, "login", lambda **_: None)
    monkeypatch.setattr(robinhood_module.robinhood_helper, "LOGGED_IN", False)
    client = RobinStocksReadClient("private-user", "private-password", None, (), str(tmp_path))

    with pytest.raises(RobinhoodProviderError) as captured:
        client.authenticate()

    assert captured.value.code == "broker_manual_approval_required"
    assert str(captured.value) == "Robinhood manual approval or trusted-session renewal is required"
    assert "private" not in str(captured.value)


def test_robinhood_adapter_normalizes_read_only_account_equity_and_option() -> None:
    client = FakeRobinhoodReadClient()
    provider = RobinhoodPortfolioProvider(
        username="not-used-by-injected-client",
        password="not-used-by-injected-client",
        client=client,
        clock=lambda: datetime(2026, 7, 19, 12, tzinfo=UTC),
    )

    accounts = provider.fetch_accounts()
    positions = provider.fetch_positions()

    assert accounts.provider == positions.provider == "robinhood"
    assert accounts.accounts[0].external_account_id == "RH-ACCOUNT-1"
    assert accounts.accounts[0].display_name == "Robinhood Individual"
    assert str(accounts.accounts[0].cash_balance) == "1250.50"
    assert str(accounts.accounts[0].cash_available_for_withdrawal) == "1000.25"
    assert str(accounts.accounts[0].buying_power) == "2500.75"
    assert str(accounts.accounts[0].account_value) == "50250.75"
    assert positions.equities[0].symbol == "AAPL"
    assert str(positions.equities[0].quantity) == "3.5"
    assert positions.option_legs[0].option_symbol == "AAPL260918C00200000"
    assert positions.option_legs[0].side == "long"
    assert accounts.provider_request_id.startswith("robinhood-accounts-")
    assert positions.provider_request_id.startswith("robinhood-positions-")
    assert client.authenticated == 2


def test_robinhood_adapter_filters_configured_accounts() -> None:
    client = FakeRobinhoodReadClient()
    provider = RobinhoodPortfolioProvider(
        username="unused",
        password="unused",
        account_numbers=("OTHER-ACCOUNT",),
        client=client,
    )

    positions = provider.fetch_positions()
    assert positions.equities == ()
    assert positions.option_legs == ()


def test_robinhood_account_classification_uses_tax_identity_not_trading_capability() -> None:
    client = FakeRobinhoodReadClient()
    client.accounts = lambda: [
        {
            "account_number": "RH-ACCOUNT-1",
            "type": "cash",
            "brokerage_account_type": "ira_roth",
        }
    ]
    provider = RobinhoodPortfolioProvider(username="unused", password="unused", client=client)

    assert provider.fetch_accounts().accounts[0].account_type == "roth_ira"


def test_robinhood_failures_never_disclose_raw_session_or_credentials() -> None:
    class FailingClient(FakeRobinhoodReadClient):
        def authenticate(self) -> None:
            raise RuntimeError("password=private access_token=private cookie=private")

    provider = RobinhoodPortfolioProvider(
        username="private-user",
        password="private-password",
        client=FailingClient(),
    )

    with pytest.raises(RobinhoodProviderError) as captured:
        provider.fetch_accounts()
    message = str(captured.value)
    assert message == "Robinhood authentication failed"
    assert captured.value.code == "broker_authentication_failed"
    assert "private" not in message
