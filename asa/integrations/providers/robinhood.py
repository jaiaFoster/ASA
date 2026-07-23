import io
from collections.abc import Callable, Mapping
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, TypeVar
from uuid import uuid4

import pyotp
import robin_stocks.robinhood as robinhood  # type: ignore[import-untyped]
from robin_stocks.robinhood import helper as robinhood_helper

from asa.application.ports.brokers import (
    BrokerAccountsResult,
    BrokerPositionsResult,
    ProviderAccount,
    ProviderEquityPosition,
    ProviderOptionLeg,
)

T = TypeVar("T")
RawRecord = Mapping[str, Any]


class RobinhoodProviderError(RuntimeError):
    """Sanitized provider failure safe for persistence and API disclosure."""


class RobinhoodReadClient(Protocol):
    def authenticate(self) -> None: ...

    def accounts(self) -> list[RawRecord]: ...

    def equity_positions(self) -> list[RawRecord]: ...

    def option_positions(self) -> list[RawRecord]: ...

    def stock_instrument(self, url: str) -> RawRecord: ...

    def option_instrument(self, option_id: str) -> RawRecord: ...


class RobinStocksReadClient:
    """Narrow read-only facade over robin_stocks; order modules are never exposed."""

    def __init__(
        self,
        username: str,
        password: str,
        totp_secret: str | None,
        account_numbers: tuple[str, ...],
    ) -> None:
        self._username = username
        self._password = password
        self._totp_secret = totp_secret
        self._account_numbers = account_numbers
        self._authenticated = False

    def authenticate(self) -> None:
        if self._authenticated:
            return
        mfa_code = None if self._totp_secret is None else pyotp.TOTP(self._totp_secret).now()
        try:
            self._quiet_call(
                robinhood.login,
                username=self._username,
                password=self._password,
                mfa_code=mfa_code,
                store_session=False,
                pickle_path="/tmp/asa-robinhood-no-session",
            )
        except RobinhoodProviderError:
            raise RobinhoodProviderError("Robinhood authentication failed") from None
        finally:
            self._username = ""
            self._password = ""
            self._totp_secret = None
        if not robinhood_helper.LOGGED_IN:
            raise RobinhoodProviderError("Robinhood authentication failed")
        self._authenticated = True

    def accounts(self) -> list[RawRecord]:
        if self._account_numbers:
            return [
                self._record(
                    self._quiet_call(
                        robinhood.load_account_profile,
                        account_number=account_number,
                    )
                )
                for account_number in self._account_numbers
            ]
        return self._records(self._quiet_call(robinhood.load_account_profile, dataType="results"))

    def equity_positions(self) -> list[RawRecord]:
        if self._account_numbers:
            return [
                item
                for account_number in self._account_numbers
                for item in self._records(
                    self._quiet_call(
                        robinhood.get_open_stock_positions,
                        account_number=account_number,
                    )
                )
            ]
        return self._records(self._quiet_call(robinhood.get_open_stock_positions))

    def option_positions(self) -> list[RawRecord]:
        if self._account_numbers:
            return [
                item
                for account_number in self._account_numbers
                for item in self._records(
                    self._quiet_call(
                        robinhood.get_open_option_positions,
                        account_number=account_number,
                    )
                )
            ]
        return self._records(self._quiet_call(robinhood.get_open_option_positions))

    def stock_instrument(self, url: str) -> RawRecord:
        return self._record(self._quiet_call(robinhood.get_instrument_by_url, url))

    def option_instrument(self, option_id: str) -> RawRecord:
        return self._record(self._quiet_call(robinhood.get_option_instrument_data_by_id, option_id))

    @staticmethod
    def _quiet_call(operation: Callable[..., T], *args: object, **kwargs: object) -> T:
        output = io.StringIO()
        try:
            with redirect_stdout(output), redirect_stderr(output):
                return operation(*args, **kwargs)
        except RobinhoodProviderError:
            raise
        except Exception:
            raise RobinhoodProviderError("Robinhood read request failed") from None

    @staticmethod
    def _record(value: object) -> RawRecord:
        if not isinstance(value, Mapping):
            raise RobinhoodProviderError("Robinhood returned an invalid record")
        return value

    @classmethod
    def _records(cls, value: object) -> list[RawRecord]:
        if not isinstance(value, list):
            raise RobinhoodProviderError("Robinhood returned an invalid collection")
        return [cls._record(item) for item in value]


class RobinhoodPortfolioProvider:
    name = "robinhood"

    def __init__(
        self,
        username: str,
        password: str,
        totp_secret: str | None = None,
        account_numbers: tuple[str, ...] = (),
        client: RobinhoodReadClient | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client or RobinStocksReadClient(
            username, password, totp_secret, account_numbers
        )
        self._account_numbers = set(account_numbers)
        self._clock = clock

    def fetch_accounts(self) -> BrokerAccountsResult:
        self._authenticate()
        received_at = self._clock()
        accounts = tuple(self._account(item, received_at) for item in self._client.accounts())
        if not accounts:
            raise RobinhoodProviderError("Robinhood returned no eligible accounts")
        return BrokerAccountsResult(
            provider=self.name,
            provider_request_id=f"robinhood-accounts-{uuid4().hex}",
            accounts=accounts,
        )

    def fetch_positions(self) -> BrokerPositionsResult:
        self._authenticate()
        received_at = self._clock()
        equities = tuple(
            position
            for item in self._client.equity_positions()
            if self._eligible_account(item)
            if (position := self._equity(item, received_at)) is not None
        )
        option_legs = tuple(
            leg
            for item in self._client.option_positions()
            if self._eligible_account(item)
            if (leg := self._option_leg(item, received_at)) is not None
        )
        return BrokerPositionsResult(
            provider=self.name,
            provider_request_id=f"robinhood-positions-{uuid4().hex}",
            equities=equities,
            option_legs=option_legs,
        )

    def _authenticate(self) -> None:
        try:
            self._client.authenticate()
        except RobinhoodProviderError:
            raise
        except Exception:
            raise RobinhoodProviderError("Robinhood authentication failed") from None

    def _account(self, item: RawRecord, received_at: datetime) -> ProviderAccount:
        account_number = self._required_text(item, "account_number")
        account_type = str(item.get("type") or "brokerage").strip().lower()
        return ProviderAccount(
            external_account_id=account_number,
            connection_id=f"robinhood:{account_number}",
            provider=self.name,
            account_type=account_type,
            display_name=f"Robinhood {account_type.title()}",
            currency="USD",
            observed_at=self._observed_at(item.get("updated_at"), received_at),
        )

    def _equity(self, item: RawRecord, received_at: datetime) -> ProviderEquityPosition | None:
        quantity = self._decimal(item.get("quantity"), required=True)
        assert quantity is not None
        if quantity == 0:
            return None
        instrument_url = self._required_text(item, "instrument")
        instrument = self._client.stock_instrument(instrument_url)
        return ProviderEquityPosition(
            external_account_id=self._required_text(item, "account_number"),
            symbol=self._required_text(instrument, "symbol"),
            quantity=quantity,
            average_cost=self._decimal(item.get("average_buy_price"), required=False),
            observed_at=self._observed_at(item.get("updated_at"), received_at),
            original_provider=self.name,
        )

    def _option_leg(self, item: RawRecord, received_at: datetime) -> ProviderOptionLeg | None:
        quantity = self._decimal(item.get("quantity"), required=True)
        assert quantity is not None
        if quantity == 0:
            return None
        option_id = self._required_text(item, "option_id")
        instrument = self._client.option_instrument(option_id)
        side = str(item.get("type") or item.get("side") or "").strip().lower()
        if side not in {"long", "short"}:
            raise RobinhoodProviderError("Robinhood option position has invalid side")
        option_symbol = str(instrument.get("symbol") or instrument.get("id") or option_id)
        strike = self._decimal(instrument.get("strike_price"), required=True)
        assert strike is not None
        return ProviderOptionLeg(
            external_account_id=self._required_text(item, "account_number"),
            underlying_symbol=self._required_text(instrument, "chain_symbol"),
            option_symbol=option_symbol,
            option_type=self._required_text(instrument, "type").lower(),
            strike=strike,
            expiration=date.fromisoformat(self._required_text(instrument, "expiration_date")),
            quantity=quantity,
            side=side,
            average_price=self._decimal(item.get("average_price"), required=False),
            observed_at=self._observed_at(item.get("updated_at"), received_at),
            original_provider=self.name,
        )

    def _eligible_account(self, item: RawRecord) -> bool:
        return not self._account_numbers or item.get("account_number") in self._account_numbers

    @staticmethod
    def _required_text(item: RawRecord, key: str) -> str:
        value = item.get(key)
        if value is None or not str(value).strip():
            raise RobinhoodProviderError(f"Robinhood record is missing required {key}")
        return str(value).strip()

    @staticmethod
    def _decimal(value: object, required: bool) -> Decimal | None:
        if value is None or value == "":
            if required:
                raise RobinhoodProviderError("Robinhood record is missing a required number")
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise RobinhoodProviderError("Robinhood record has an invalid number") from None

    @staticmethod
    def _observed_at(value: object, fallback: datetime) -> datetime:
        if value is None:
            return fallback
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise RobinhoodProviderError(
                "Robinhood record has an invalid observation time"
            ) from None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
