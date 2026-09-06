from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"


class AccountHoldingsStatus(StrEnum):
    """One account's own truthful fetch outcome (STOCK-RUNTIME-001 STK-04).

    SUCCESS/SUCCESS_EMPTY are both genuine, current data -- the only
    difference is whether this account happens to hold anything right now.
    STALE_FALLBACK means the most recent refresh attempt failed and this is
    the last known-good snapshot for this account; STALE means nobody has
    refreshed recently but no refresh is known to have failed. A wholly
    unseen portfolio (never any successful run) has no accounts to report
    a per-account status for at all -- that case surfaces at the portfolio
    level (no publication exists), never fabricated here.
    """

    SUCCESS = "success"
    SUCCESS_EMPTY = "success_empty"
    STALE_FALLBACK = "stale_fallback"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class AccountHoldingsSummary:
    status: AccountHoldingsStatus
    as_of: datetime


def account_holdings_status(
    *,
    account_observed_at: datetime,
    has_positions: bool,
    now: datetime,
    fresh_for: timedelta,
    serving_last_success: bool,
) -> AccountHoldingsStatus:
    """Pure derivation from already-known evidence -- no acquisition, no
    clock read, no fabricated failure isolation the underlying single-call
    broker fetch doesn't actually support (see project/reports/
    STOCK-RUNTIME-001-STK-04.md).
    """
    if account_observed_at >= now - fresh_for:
        if has_positions:
            return AccountHoldingsStatus.SUCCESS
        return AccountHoldingsStatus.SUCCESS_EMPTY
    if serving_last_success:
        return AccountHoldingsStatus.STALE_FALLBACK
    return AccountHoldingsStatus.STALE


def mask_account_identifier(value: str) -> str:
    """Never expose a raw broker account identifier outside the system
    boundary (API responses, application logs) -- at most the last four
    characters survive, matching the masking convention brokerages
    themselves use. Internal persistence keeps the real value: this is a
    presentation/logging-boundary transform, not a storage change.
    """
    trimmed = value.strip()
    if len(trimmed) <= 4:
        return "*" * len(trimmed)
    return f"{'*' * (len(trimmed) - 4)}{trimmed[-4:]}"


@dataclass(frozen=True, slots=True)
class BrokerAccount:
    id: UUID
    connection_id: str
    external_account_id: str
    provider: str
    account_type: str
    display_name: str
    currency: str
    cash_balance: Decimal | None
    cash_available_for_withdrawal: Decimal | None
    buying_power: Decimal | None
    account_value: Decimal | None
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
