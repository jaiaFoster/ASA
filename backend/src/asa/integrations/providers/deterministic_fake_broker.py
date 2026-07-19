from datetime import UTC, date, datetime
from decimal import Decimal

from asa.application.ports.brokers import (
    BrokerAccountsResult,
    BrokerPositionsResult,
    ProviderAccount,
    ProviderEquityPosition,
    ProviderOptionLeg,
)


class DeterministicFakeBrokerPortfolioProvider:
    name = "deterministic_fake_broker"
    observed_at = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)

    def fetch_accounts(self) -> BrokerAccountsResult:
        return BrokerAccountsResult(
            provider=self.name,
            provider_request_id="fake-broker-accounts-001",
            accounts=(
                ProviderAccount(
                    external_account_id="taxable-001",
                    connection_id="fake-connection-primary",
                    provider=self.name,
                    account_type="taxable",
                    display_name="Primary Taxable",
                    currency="USD",
                    observed_at=self.observed_at,
                ),
            ),
        )

    def fetch_positions(self) -> BrokerPositionsResult:
        return BrokerPositionsResult(
            provider=self.name,
            provider_request_id="fake-broker-positions-001",
            equities=(
                ProviderEquityPosition(
                    external_account_id="taxable-001",
                    symbol="AAPL",
                    quantity=Decimal("12"),
                    average_cost=Decimal("172.50"),
                    observed_at=self.observed_at,
                    original_provider=self.name,
                ),
            ),
            option_legs=(
                ProviderOptionLeg(
                    external_account_id="taxable-001",
                    underlying_symbol="AAPL",
                    option_symbol="AAPL260918C00200000",
                    option_type="call",
                    strike=Decimal("200"),
                    expiration=date(2026, 9, 18),
                    quantity=Decimal("1"),
                    side="long",
                    average_price=Decimal("8.40"),
                    observed_at=self.observed_at,
                    original_provider=self.name,
                ),
                ProviderOptionLeg(
                    external_account_id="taxable-001",
                    underlying_symbol="AAPL",
                    option_symbol="AAPL260918C00210000",
                    option_type="call",
                    strike=Decimal("210"),
                    expiration=date(2026, 9, 18),
                    quantity=Decimal("1"),
                    side="short",
                    average_price=Decimal("5.10"),
                    observed_at=self.observed_at,
                    original_provider=self.name,
                ),
            ),
        )
