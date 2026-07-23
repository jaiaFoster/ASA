from datetime import UTC, datetime

import pytest

from asa.integrations.providers.robinhood import (
    RobinhoodPortfolioProvider,
    RobinhoodProviderError,
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
                "updated_at": "2026-07-19T11:00:00Z",
            }
        ]

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
    assert "private" not in message
