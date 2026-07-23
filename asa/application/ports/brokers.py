from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProviderAccount:
    external_account_id: str
    connection_id: str
    provider: str
    account_type: str
    display_name: str
    currency: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ProviderEquityPosition:
    external_account_id: str
    symbol: str
    quantity: Decimal
    average_cost: Decimal | None
    observed_at: datetime
    original_provider: str


@dataclass(frozen=True, slots=True)
class ProviderOptionLeg:
    external_account_id: str
    underlying_symbol: str
    option_symbol: str
    option_type: str
    strike: Decimal
    expiration: date
    quantity: Decimal
    side: str
    average_price: Decimal | None
    observed_at: datetime
    original_provider: str


@dataclass(frozen=True, slots=True)
class BrokerAccountsResult:
    provider: str
    provider_request_id: str
    accounts: tuple[ProviderAccount, ...]


@dataclass(frozen=True, slots=True)
class BrokerPositionsResult:
    provider: str
    provider_request_id: str
    equities: tuple[ProviderEquityPosition, ...]
    option_legs: tuple[ProviderOptionLeg, ...]


class BrokerPortfolioProvider(Protocol):
    name: str

    def fetch_accounts(self) -> BrokerAccountsResult: ...

    def fetch_positions(self) -> BrokerPositionsResult: ...
