from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class BrokerAccount:
    id: UUID
    connection_id: str
    external_account_id: str
    provider: str
    account_type: str
    display_name: str
    currency: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class EquityPosition:
    account_id: UUID
    symbol: str
    quantity: Decimal
    average_cost: Decimal | None
    observed_at: datetime
    original_provider: str


@dataclass(frozen=True, slots=True)
class OptionPositionLeg:
    account_id: UUID
    underlying_symbol: str
    option_symbol: str
    option_type: OptionType
    strike: Decimal
    expiration: date
    quantity: Decimal
    side: PositionSide
    average_price: Decimal | None
    observed_at: datetime
    original_provider: str


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    observed_at: datetime
    provider: str
    provider_request_id: str
    accounts: tuple[BrokerAccount, ...]
    equity_positions: tuple[EquityPosition, ...]
    option_legs: tuple[OptionPositionLeg, ...]


@dataclass(frozen=True, slots=True)
class PublishedPortfolio:
    publication_id: UUID
    run_id: UUID
    snapshot_id: UUID
    published_at: datetime
    snapshot: PortfolioSnapshot


def validate_snapshot(snapshot: PortfolioSnapshot) -> None:
    if not snapshot.accounts:
        raise ValueError("portfolio requires at least one account")
    account_ids = {account.id for account in snapshot.accounts}
    if len(account_ids) != len(snapshot.accounts):
        raise ValueError("portfolio account identifiers must be unique")
    for equity in snapshot.equity_positions:
        if equity.account_id not in account_ids:
            raise ValueError("every position must reference one snapshot account")
    for option_leg in snapshot.option_legs:
        if option_leg.account_id not in account_ids:
            raise ValueError("every position must reference one snapshot account")
    for leg in snapshot.option_legs:
        if not leg.option_symbol or leg.expiration is None:
            raise ValueError("option legs require symbol and expiration")
