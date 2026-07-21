"""Immutable provider-neutral financial contracts (ASA-ARCH-005).

This module owns structural values, validation, canonical serialization, and
deterministic identity only.  It deliberately contains no acquisition,
calculation, reconciliation, strategy, portfolio, or execution behavior.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, TypeAlias, cast

from domain.operational import CanonicalInstrumentIdentity, Instrument, InstrumentKind
from domain.references import EvidenceKind, EvidenceReference
from domain.values import DomainInvariantError, require_finite_decimal, require_tz_aware

FINANCIAL_CONTRACT_VERSION = "v1"


class FinancialContractSerializationError(ValueError):
    """Canonical financial-contract bytes cannot be decoded safely."""


class SecurityAssetType(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    CASH = "cash"


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


class AnnouncementTime(str, Enum):
    BEFORE_OPEN = "before_open"
    DURING_MARKET = "during_market"
    AFTER_CLOSE = "after_close"
    UNKNOWN = "unknown"


class OptionLegPosition(str, Enum):
    LONG = "long"
    SHORT = "short"


class OptionStructureType(str, Enum):
    SINGLE_LEG = "single_leg"
    VERTICAL = "vertical"
    CALENDAR = "calendar"
    DIAGONAL = "diagonal"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    COVERED_CALL = "covered_call"
    CASH_SECURED_PUT = "cash_secured_put"


def _text(value: object, owner: str, field_name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DomainInvariantError(f"{owner}.{field_name} must be non-empty normalized text")


def _enum(value: object, expected: type[Enum], owner: str, field_name: str) -> None:
    if not isinstance(value, expected):
        raise DomainInvariantError(f"{owner}.{field_name} must be a {expected.__name__}")


def _decimal(
    value: object,
    owner: str,
    field_name: str,
    *,
    positive: bool = False,
    unit_interval: bool = False,
) -> None:
    require_finite_decimal(value, owner, field_name)
    number = cast(Decimal, value)
    if positive and number <= 0:
        raise DomainInvariantError(f"{owner}.{field_name} must be greater than zero")
    if not positive and number < 0:
        raise DomainInvariantError(f"{owner}.{field_name} cannot be negative")
    if unit_interval and number > 1:
        raise DomainInvariantError(f"{owner}.{field_name} must be within [0, 1]")


def _optional_decimal(
    value: object,
    owner: str,
    field_name: str,
    *,
    unit_interval: bool = False,
    signed: bool = False,
) -> None:
    if value is None:
        return
    require_finite_decimal(value, owner, field_name)
    number = cast(Decimal, value)
    if not signed and number < 0:
        raise DomainInvariantError(f"{owner}.{field_name} cannot be negative")
    if unit_interval and number > 1:
        raise DomainInvariantError(f"{owner}.{field_name} must be within [0, 1]")


def _optional_count(value: object, owner: str, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainInvariantError(f"{owner}.{field_name} must be a non-negative integer")


def _evidence_key(value: EvidenceReference) -> tuple[str, str, int]:
    return (value.kind.value, value.referenced_id, value.version or 0)


def _evidence(values: tuple[EvidenceReference, ...], owner: str) -> tuple[EvidenceReference, ...]:
    if not isinstance(values, tuple) or not values:
        raise DomainInvariantError(f"{owner}.evidence cannot be empty")
    if not all(isinstance(value, EvidenceReference) for value in values):
        raise DomainInvariantError(f"{owner}.evidence must contain EvidenceReference records")
    normalized = tuple(sorted(values, key=_evidence_key))
    if len(normalized) != len(set(normalized)):
        raise DomainInvariantError(f"{owner}.evidence contains duplicates")
    return normalized


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _hash(namespace: str, value: object) -> str:
    payload = {
        "identity_namespace": namespace,
        "identity_version": FINANCIAL_CONTRACT_VERSION,
        "value": value,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class Security:
    instrument: Instrument
    symbol: str
    asset_type: SecurityAssetType
    exchange: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("Security.instrument must be an Instrument")
        _text(self.symbol, "Security", "symbol")
        if self.symbol != self.symbol.upper():
            raise DomainInvariantError("Security.symbol must be uppercase")
        _enum(self.asset_type, SecurityAssetType, "Security", "asset_type")
        _text(self.exchange, "Security", "exchange")
        if self.instrument.kind is InstrumentKind.OPTION:
            raise DomainInvariantError("Security.instrument cannot be an option")
        expected = {
            SecurityAssetType.EQUITY: InstrumentKind.EQUITY,
            SecurityAssetType.ETF: InstrumentKind.EQUITY,
            SecurityAssetType.INDEX: InstrumentKind.EQUITY,
            SecurityAssetType.CASH: InstrumentKind.CASH,
        }[self.asset_type]
        if self.instrument.kind is not expected:
            raise DomainInvariantError("Security.asset_type does not match Instrument.kind")

    @property
    def identity(self) -> str:
        return _hash(
            "asa.security",
            {
                "asset_type": self.asset_type.value,
                "exchange": self.exchange,
                "instrument_identity": _identity_data(self.instrument.identity),
                "symbol": self.symbol,
            },
        )


@dataclass(frozen=True, slots=True)
class SecurityCollection:
    securities: tuple[Security, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted(self.securities, key=lambda item: item.identity))
        if not all(isinstance(item, Security) for item in normalized):
            raise DomainInvariantError("SecurityCollection must contain Security records")
        identities = tuple(item.identity for item in normalized)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("SecurityCollection contains duplicate securities")
        object.__setattr__(self, "securities", normalized)

    @property
    def identity(self) -> str:
        return _hash("asa.security_collection", [item.identity for item in self.securities])


@dataclass(frozen=True, slots=True)
class OptionContract:
    option_contract_id: CanonicalInstrumentIdentity
    underlying: Security
    expiration: date
    strike: Decimal
    option_type: OptionType
    bid: Decimal | None
    ask: Decimal | None
    mark: Decimal | None
    volume: int | None
    open_interest: int | None
    delta: Decimal | None
    gamma: Decimal | None
    theta: Decimal | None
    vega: Decimal | None
    rho: Decimal | None
    implied_volatility: Decimal | None
    observed_at: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.option_contract_id, CanonicalInstrumentIdentity):
            raise DomainInvariantError(
                "OptionContract.option_contract_id must be a CanonicalInstrumentIdentity"
            )
        if not isinstance(self.underlying, Security):
            raise DomainInvariantError("OptionContract.underlying must be a Security")
        if not isinstance(self.expiration, date) or isinstance(self.expiration, datetime):
            raise DomainInvariantError("OptionContract.expiration must be a date")
        _decimal(self.strike, "OptionContract", "strike", positive=True)
        _enum(self.option_type, OptionType, "OptionContract", "option_type")
        for name in ("bid", "ask", "mark", "implied_volatility"):
            _optional_decimal(getattr(self, name), "OptionContract", name)
        for name in ("delta", "gamma", "theta", "vega", "rho"):
            _optional_decimal(getattr(self, name), "OptionContract", name, signed=True)
        _optional_count(self.volume, "OptionContract", "volume")
        _optional_count(self.open_interest, "OptionContract", "open_interest")
        require_tz_aware(self.observed_at, "OptionContract", "observed_at")
        if self.expiration < _utc(self.observed_at).date():
            raise DomainInvariantError("OptionContract.expiration cannot precede observed_at")
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise DomainInvariantError("OptionContract market cannot be crossed")
        object.__setattr__(self, "evidence", _evidence(self.evidence, "OptionContract"))

    @property
    def identity(self) -> str:
        return _hash("asa.option_contract", _option_natural_data(self))

    @property
    def observation_identity(self) -> str:
        return _hash("asa.option_contract_observation", financial_contract_to_data(self))


def _option_sort_key(value: OptionContract) -> tuple[object, ...]:
    return (
        value.expiration,
        value.strike,
        value.option_type.value,
        value.option_contract_id.scheme,
        value.option_contract_id.value,
    )


@dataclass(frozen=True, slots=True)
class OptionCollection:
    contracts: tuple[OptionContract, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted(self.contracts, key=_option_sort_key))
        if not all(isinstance(item, OptionContract) for item in normalized):
            raise DomainInvariantError("OptionCollection must contain OptionContract records")
        identities = tuple(item.identity for item in normalized)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("OptionCollection contains duplicate contracts")
        object.__setattr__(self, "contracts", normalized)

    @property
    def identity(self) -> str:
        return _hash(
            "asa.option_collection", [item.observation_identity for item in self.contracts]
        )


@dataclass(frozen=True, slots=True)
class OptionChain:
    option_chain_id: str
    underlying: Security
    observed_at: datetime
    contracts: tuple[OptionContract, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _text(self.option_chain_id, "OptionChain", "option_chain_id")
        if not isinstance(self.underlying, Security):
            raise DomainInvariantError("OptionChain.underlying must be a Security")
        require_tz_aware(self.observed_at, "OptionChain", "observed_at")
        normalized = OptionCollection(self.contracts).contracts
        if any(item.underlying.identity != self.underlying.identity for item in normalized):
            raise DomainInvariantError("OptionChain contracts must share the chain underlying")
        if any(item.observed_at != self.observed_at for item in normalized):
            raise DomainInvariantError("OptionChain contracts must share observed_at")
        object.__setattr__(self, "contracts", normalized)
        object.__setattr__(self, "evidence", _evidence(self.evidence, "OptionChain"))

    @property
    def identity(self) -> str:
        return _hash("asa.option_chain", financial_contract_to_data(self))

    def find(
        self,
        *,
        expiration: date | None = None,
        strike: Decimal | None = None,
        option_type: OptionType | None = None,
    ) -> tuple[OptionContract, ...]:
        """Pure deterministic value lookup over the immutable canonical tuple."""
        return tuple(
            item
            for item in self.contracts
            if (expiration is None or item.expiration == expiration)
            and (strike is None or item.strike == strike)
            and (option_type is None or item.option_type is option_type)
        )


@dataclass(frozen=True, slots=True)
class ExpirationCycle:
    expiration_date: date
    days_to_expiration: int
    monthly: bool
    weekly: bool
    as_of: date
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.expiration_date, date) or isinstance(self.expiration_date, datetime):
            raise DomainInvariantError("ExpirationCycle.expiration_date must be a date")
        if not isinstance(self.as_of, date) or isinstance(self.as_of, datetime):
            raise DomainInvariantError("ExpirationCycle.as_of must be a date")
        if isinstance(self.days_to_expiration, bool) or not isinstance(
            self.days_to_expiration, int
        ):
            raise DomainInvariantError("ExpirationCycle.days_to_expiration must be an integer")
        if self.days_to_expiration < 0:
            raise DomainInvariantError("ExpirationCycle.days_to_expiration cannot be negative")
        if self.days_to_expiration != (self.expiration_date - self.as_of).days:
            raise DomainInvariantError("ExpirationCycle.days_to_expiration must equal date delta")
        if not isinstance(self.monthly, bool) or not isinstance(self.weekly, bool):
            raise DomainInvariantError("ExpirationCycle classifications must be booleans")
        if not (self.monthly or self.weekly):
            raise DomainInvariantError(
                "ExpirationCycle requires a monthly or weekly classification"
            )
        object.__setattr__(self, "evidence", _evidence(self.evidence, "ExpirationCycle"))

    @property
    def identity(self) -> str:
        return _hash("asa.expiration_cycle", financial_contract_to_data(self))


@dataclass(frozen=True, slots=True)
class ExpirationCollection:
    as_of: date
    cycles: tuple[ExpirationCycle, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.as_of, date) or isinstance(self.as_of, datetime):
            raise DomainInvariantError("ExpirationCollection.as_of must be a date")
        normalized = tuple(
            sorted(
                self.cycles,
                key=lambda item: (
                    item.expiration_date,
                    item.monthly,
                    item.weekly,
                    item.identity,
                ),
            )
        )
        if not all(isinstance(item, ExpirationCycle) for item in normalized):
            raise DomainInvariantError("ExpirationCollection must contain ExpirationCycle records")
        if any(item.as_of != self.as_of for item in normalized):
            raise DomainInvariantError("ExpirationCollection cycles must share as_of")
        identities = tuple(item.identity for item in normalized)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("ExpirationCollection contains duplicate cycles")
        object.__setattr__(self, "cycles", normalized)

    @property
    def identity(self) -> str:
        return _hash("asa.expiration_collection", financial_contract_to_data(self))


@dataclass(frozen=True, slots=True)
class EarningsHistoryEntry:
    earnings_date: date
    announcement_time: AnnouncementTime
    realized_move: Decimal | None
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.earnings_date, date) or isinstance(self.earnings_date, datetime):
            raise DomainInvariantError("EarningsHistoryEntry.earnings_date must be a date")
        _enum(
            self.announcement_time,
            AnnouncementTime,
            "EarningsHistoryEntry",
            "announcement_time",
        )
        _optional_decimal(self.realized_move, "EarningsHistoryEntry", "realized_move")
        object.__setattr__(self, "evidence", _evidence(self.evidence, "EarningsHistoryEntry"))


@dataclass(frozen=True, slots=True)
class EarningsEvent:
    earnings_event_id: str
    security: Security
    earnings_date: date
    announcement_time: AnnouncementTime
    estimated_move: Decimal | None
    confirmed: bool
    historical_sequence: tuple[EarningsHistoryEntry, ...]
    observed_at: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _text(self.earnings_event_id, "EarningsEvent", "earnings_event_id")
        if not isinstance(self.security, Security):
            raise DomainInvariantError("EarningsEvent.security must be a Security")
        if not isinstance(self.earnings_date, date) or isinstance(self.earnings_date, datetime):
            raise DomainInvariantError("EarningsEvent.earnings_date must be a date")
        _enum(self.announcement_time, AnnouncementTime, "EarningsEvent", "announcement_time")
        _optional_decimal(self.estimated_move, "EarningsEvent", "estimated_move")
        if not isinstance(self.confirmed, bool):
            raise DomainInvariantError("EarningsEvent.confirmed must be a boolean")
        require_tz_aware(self.observed_at, "EarningsEvent", "observed_at")
        normalized = tuple(
            sorted(self.historical_sequence, key=lambda item: item.earnings_date, reverse=True)
        )
        if not all(isinstance(item, EarningsHistoryEntry) for item in normalized):
            raise DomainInvariantError(
                "EarningsEvent.historical_sequence must contain EarningsHistoryEntry records"
            )
        dates = tuple(item.earnings_date for item in normalized)
        if any(value >= self.earnings_date for value in dates):
            raise DomainInvariantError("EarningsEvent history must precede the event")
        if len(dates) != len(set(dates)):
            raise DomainInvariantError("EarningsEvent history contains duplicate dates")
        object.__setattr__(self, "historical_sequence", normalized)
        object.__setattr__(self, "evidence", _evidence(self.evidence, "EarningsEvent"))

    @property
    def identity(self) -> str:
        return _hash(
            "asa.earnings_event",
            {
                "security_identity": _identity_data(self.security.instrument.identity),
                "earnings_date": self.earnings_date.isoformat(),
            },
        )

    @property
    def observation_identity(self) -> str:
        return _hash("asa.earnings_event_observation", financial_contract_to_data(self))


@dataclass(frozen=True, slots=True)
class EarningsCalendar:
    start_date: date
    end_date: date
    observed_at: datetime
    events: tuple[EarningsEvent, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for name in ("start_date", "end_date"):
            value = getattr(self, name)
            if not isinstance(value, date) or isinstance(value, datetime):
                raise DomainInvariantError(f"EarningsCalendar.{name} must be a date")
        if self.end_date < self.start_date:
            raise DomainInvariantError("EarningsCalendar date window is invalid")
        require_tz_aware(self.observed_at, "EarningsCalendar", "observed_at")
        normalized = tuple(
            sorted(
                self.events,
                key=lambda item: (item.earnings_date, item.security.identity),
            )
        )
        if not all(isinstance(item, EarningsEvent) for item in normalized):
            raise DomainInvariantError("EarningsCalendar must contain EarningsEvent records")
        if any(not self.start_date <= item.earnings_date <= self.end_date for item in normalized):
            raise DomainInvariantError("EarningsCalendar event is outside the date window")
        if any(item.observed_at != self.observed_at for item in normalized):
            raise DomainInvariantError("EarningsCalendar events must share observed_at")
        identities = tuple(item.identity for item in normalized)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("EarningsCalendar contains duplicate events")
        object.__setattr__(self, "events", normalized)
        object.__setattr__(self, "evidence", _evidence(self.evidence, "EarningsCalendar"))

    @property
    def identity(self) -> str:
        return _hash("asa.earnings_calendar", financial_contract_to_data(self))


@dataclass(frozen=True, slots=True)
class VolatilityEvidence:
    security: Security
    implied_volatility: Decimal | None
    historical_volatility: Decimal | None
    iv_rank: Decimal | None
    iv_percentile: Decimal | None
    lookback: timedelta
    observed_at: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.security, Security):
            raise DomainInvariantError("VolatilityEvidence.security must be a Security")
        _optional_decimal(self.implied_volatility, "VolatilityEvidence", "implied_volatility")
        _optional_decimal(self.historical_volatility, "VolatilityEvidence", "historical_volatility")
        _optional_decimal(self.iv_rank, "VolatilityEvidence", "iv_rank", unit_interval=True)
        _optional_decimal(
            self.iv_percentile,
            "VolatilityEvidence",
            "iv_percentile",
            unit_interval=True,
        )
        if all(
            value is None
            for value in (
                self.implied_volatility,
                self.historical_volatility,
                self.iv_rank,
                self.iv_percentile,
            )
        ):
            raise DomainInvariantError("VolatilityEvidence requires at least one value")
        if not isinstance(self.lookback, timedelta) or self.lookback <= timedelta(0):
            raise DomainInvariantError("VolatilityEvidence.lookback must be a positive duration")
        require_tz_aware(self.observed_at, "VolatilityEvidence", "observed_at")
        object.__setattr__(self, "evidence", _evidence(self.evidence, "VolatilityEvidence"))

    @property
    def identity(self) -> str:
        return _hash("asa.volatility_evidence", financial_contract_to_data(self))


@dataclass(frozen=True, slots=True)
class OptionLeg:
    contract: OptionContract
    position: OptionLegPosition
    quantity: Decimal
    role: str

    def __post_init__(self) -> None:
        if not isinstance(self.contract, OptionContract):
            raise DomainInvariantError("OptionLeg.contract must be an OptionContract")
        _enum(self.position, OptionLegPosition, "OptionLeg", "position")
        _decimal(self.quantity, "OptionLeg", "quantity", positive=True)
        _text(self.role, "OptionLeg", "role")

    @property
    def identity(self) -> str:
        return _hash("asa.option_leg", financial_contract_to_data(self))


def _leg_sort_key(value: OptionLeg) -> tuple[object, ...]:
    return (
        value.role,
        value.contract.expiration,
        value.contract.strike,
        value.contract.option_type.value,
        value.position.value,
        value.contract.identity,
    )


@dataclass(frozen=True, slots=True)
class OptionStructure:
    option_structure_id: str
    structure_type: OptionStructureType
    underlying: Security
    legs: tuple[OptionLeg, ...]
    observed_at: datetime
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _text(self.option_structure_id, "OptionStructure", "option_structure_id")
        _enum(self.structure_type, OptionStructureType, "OptionStructure", "structure_type")
        if not isinstance(self.underlying, Security):
            raise DomainInvariantError("OptionStructure.underlying must be a Security")
        require_tz_aware(self.observed_at, "OptionStructure", "observed_at")
        normalized = tuple(sorted(self.legs, key=_leg_sort_key))
        if not all(isinstance(item, OptionLeg) for item in normalized):
            raise DomainInvariantError("OptionStructure.legs must contain OptionLeg records")
        if any(
            item.contract.underlying.identity != self.underlying.identity for item in normalized
        ):
            raise DomainInvariantError("OptionStructure legs must share the structure underlying")
        if any(item.contract.observed_at != self.observed_at for item in normalized):
            raise DomainInvariantError("OptionStructure legs must share observed_at")
        keys = tuple(
            (item.contract.identity, item.position.value, item.role) for item in normalized
        )
        if len(keys) != len(set(keys)):
            raise DomainInvariantError("OptionStructure contains duplicate legs")
        object.__setattr__(self, "legs", normalized)
        object.__setattr__(self, "evidence", _evidence(self.evidence, "OptionStructure"))
        self._validate_shape()

    def _validate_shape(self) -> None:
        legs = self.legs
        kind = self.structure_type
        if kind in {
            OptionStructureType.SINGLE_LEG,
            OptionStructureType.COVERED_CALL,
            OptionStructureType.CASH_SECURED_PUT,
        }:
            if len(legs) != 1:
                raise DomainInvariantError(f"OptionStructure {kind.value} requires one leg")
            if kind is OptionStructureType.COVERED_CALL and (
                legs[0].contract.option_type is not OptionType.CALL
                or legs[0].position is not OptionLegPosition.SHORT
            ):
                raise DomainInvariantError("OptionStructure covered_call requires one short call")
            if kind is OptionStructureType.CASH_SECURED_PUT and (
                legs[0].contract.option_type is not OptionType.PUT
                or legs[0].position is not OptionLegPosition.SHORT
            ):
                raise DomainInvariantError(
                    "OptionStructure cash_secured_put requires one short put"
                )
            return
        if len(legs) != 2:
            raise DomainInvariantError(f"OptionStructure {kind.value} requires two legs")
        first, second = legs
        same_expiry = first.contract.expiration == second.contract.expiration
        same_strike = first.contract.strike == second.contract.strike
        same_type = first.contract.option_type is second.contract.option_type
        call_put = {first.contract.option_type, second.contract.option_type} == {
            OptionType.CALL,
            OptionType.PUT,
        }
        valid = {
            OptionStructureType.VERTICAL: same_expiry and same_type and not same_strike,
            OptionStructureType.CALENDAR: same_strike and same_type and not same_expiry,
            OptionStructureType.DIAGONAL: same_type and not same_strike and not same_expiry,
            OptionStructureType.STRADDLE: call_put and same_strike and same_expiry,
            OptionStructureType.STRANGLE: call_put and not same_strike and same_expiry,
        }[kind]
        if not valid:
            raise DomainInvariantError(f"OptionStructure {kind.value} shape is invalid")

    @property
    def identity(self) -> str:
        return _hash("asa.option_structure", financial_contract_to_data(self))


FinancialContract: TypeAlias = (
    Security
    | SecurityCollection
    | OptionContract
    | OptionCollection
    | OptionChain
    | ExpirationCycle
    | ExpirationCollection
    | EarningsHistoryEntry
    | EarningsEvent
    | EarningsCalendar
    | VolatilityEvidence
    | OptionLeg
    | OptionStructure
)

_FINANCIAL_CONTRACT_TYPES = (
    Security,
    SecurityCollection,
    OptionContract,
    OptionCollection,
    OptionChain,
    ExpirationCycle,
    ExpirationCollection,
    EarningsHistoryEntry,
    EarningsEvent,
    EarningsCalendar,
    VolatilityEvidence,
    OptionLeg,
    OptionStructure,
)


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _identity_data(value: CanonicalInstrumentIdentity) -> dict[str, str]:
    return {"scheme": value.scheme, "value": value.value}


def _instrument_data(value: Instrument) -> dict[str, object]:
    return {
        "currency": value.currency,
        "display_symbol": value.display_symbol,
        "identity": _identity_data(value.identity),
        "kind": value.kind.value,
        "sector": None
        if value.sector is None
        else {
            "code": value.sector.code,
            "taxonomy": value.sector.taxonomy,
            "taxonomy_version": value.sector.taxonomy_version,
        },
        "underlying_identity": None
        if value.underlying_identity is None
        else _identity_data(value.underlying_identity),
    }


def _security_data(value: Security) -> dict[str, object]:
    return {
        "asset_type": value.asset_type.value,
        "exchange": value.exchange,
        "instrument": _instrument_data(value.instrument),
        "symbol": value.symbol,
    }


def _evidence_data(value: EvidenceReference) -> dict[str, object]:
    return {
        "kind": value.kind.value,
        "referenced_id": value.referenced_id,
        "version": value.version,
    }


def _option_natural_data(value: OptionContract) -> dict[str, object]:
    return {
        "canonical_id": _identity_data(value.option_contract_id),
        "expiration": value.expiration.isoformat(),
        "option_type": value.option_type.value,
        "strike": _decimal_text(value.strike),
        "underlying_identity": _identity_data(value.underlying.instrument.identity),
    }


def _wire(value: object) -> object:
    if isinstance(value, Decimal):
        return {"$decimal": _decimal_text(value)}
    if isinstance(value, datetime):
        return {"$instant": _utc(value).isoformat().replace("+00:00", "Z")}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, timedelta):
        return {
            "$duration": {
                "days": value.days,
                "seconds": value.seconds,
                "microseconds": value.microseconds,
            }
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, CanonicalInstrumentIdentity):
        return {"$canonical_instrument_identity": _identity_data(value)}
    if isinstance(value, Instrument):
        return {"$instrument": _instrument_data(value)}
    if isinstance(value, EvidenceReference):
        return {"$evidence": _evidence_data(value)}
    if isinstance(value, tuple):
        return [_wire(item) for item in value]
    if isinstance(value, _FINANCIAL_CONTRACT_TYPES):
        return financial_contract_to_data(value)
    return value


def financial_contract_to_data(value: FinancialContract) -> dict[str, object]:
    """Return a closed tagged canonical JSON-compatible record."""
    return {
        "contract_type": type(value).__name__,
        "contract_version": FINANCIAL_CONTRACT_VERSION,
        "fields": {item.name: _wire(getattr(value, item.name)) for item in fields(value)},
    }


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def serialize_financial_contract(value: FinancialContract) -> bytes:
    return _canonical_json(financial_contract_to_data(value))


def _object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise FinancialContractSerializationError(f"{path} must be an object")
    return cast(dict[str, object], value)


def _decode(value: object) -> object:
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        return value
    item = cast(dict[str, object], value)
    if set(item) == {"$decimal"}:
        try:
            number = Decimal(cast(str, item["$decimal"]))
        except (InvalidOperation, TypeError) as exc:
            raise FinancialContractSerializationError("invalid canonical Decimal") from exc
        if not number.is_finite() or _decimal_text(number) != item["$decimal"]:
            raise FinancialContractSerializationError("non-canonical Decimal")
        return number
    if set(item) == {"$date"}:
        try:
            return date.fromisoformat(cast(str, item["$date"]))
        except (TypeError, ValueError) as exc:
            raise FinancialContractSerializationError("invalid canonical date") from exc
    if set(item) == {"$instant"}:
        try:
            instant = datetime.fromisoformat(cast(str, item["$instant"]).replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise FinancialContractSerializationError("invalid canonical instant") from exc
        require_tz_aware(instant, "financial_contract", "instant")
        return instant
    if set(item) == {"$duration"}:
        duration = _object(item["$duration"], "duration")
        if set(duration) != {"days", "seconds", "microseconds"} or any(
            isinstance(value, bool) or not isinstance(value, int) for value in duration.values()
        ):
            raise FinancialContractSerializationError("invalid canonical duration")
        return timedelta(
            days=cast(int, duration["days"]),
            seconds=cast(int, duration["seconds"]),
            microseconds=cast(int, duration["microseconds"]),
        )
    if set(item) == {"$canonical_instrument_identity"}:
        identity = _object(item["$canonical_instrument_identity"], "identity")
        if set(identity) != {"scheme", "value"}:
            raise FinancialContractSerializationError("invalid canonical instrument identity")
        return CanonicalInstrumentIdentity(
            cast(str, identity["scheme"]), cast(str, identity["value"])
        )
    if set(item) == {"$evidence"}:
        evidence = _object(item["$evidence"], "evidence")
        if set(evidence) != {"kind", "referenced_id", "version"}:
            raise FinancialContractSerializationError("invalid evidence reference")
        return EvidenceReference(
            EvidenceKind(cast(str, evidence["kind"])),
            cast(str, evidence["referenced_id"]),
            cast(int | None, evidence["version"]),
        )
    if set(item) == {"$instrument"}:
        from domain.operational import SectorClassification

        data = _object(item["$instrument"], "instrument")
        expected = {
            "currency",
            "display_symbol",
            "identity",
            "kind",
            "sector",
            "underlying_identity",
        }
        if set(data) != expected:
            raise FinancialContractSerializationError("invalid Instrument fields")
        identity_data = _object(data["identity"], "instrument.identity")
        underlying_data = data["underlying_identity"]
        sector_data = data["sector"]
        return Instrument(
            CanonicalInstrumentIdentity(
                cast(str, identity_data["scheme"]), cast(str, identity_data["value"])
            ),
            InstrumentKind(cast(str, data["kind"])),
            cast(str, data["display_symbol"]),
            cast(str, data["currency"]),
            None
            if sector_data is None
            else SectorClassification(
                cast(str, _object(sector_data, "instrument.sector")["taxonomy"]),
                cast(str, _object(sector_data, "instrument.sector")["taxonomy_version"]),
                cast(str, _object(sector_data, "instrument.sector")["code"]),
            ),
            None
            if underlying_data is None
            else CanonicalInstrumentIdentity(
                cast(str, _object(underlying_data, "underlying")["scheme"]),
                cast(str, _object(underlying_data, "underlying")["value"]),
            ),
        )
    if set(item) == {"contract_type", "contract_version", "fields"}:
        return _contract_from_data(item)
    raise FinancialContractSerializationError("unknown tagged financial value")


_ENUM_FIELDS: dict[tuple[str, str], type[Enum]] = {
    ("Security", "asset_type"): SecurityAssetType,
    ("OptionContract", "option_type"): OptionType,
    ("EarningsHistoryEntry", "announcement_time"): AnnouncementTime,
    ("EarningsEvent", "announcement_time"): AnnouncementTime,
    ("OptionLeg", "position"): OptionLegPosition,
    ("OptionStructure", "structure_type"): OptionStructureType,
}

_CONTRACT_TYPES: dict[str, type[Any]] = {
    value.__name__: value for value in _FINANCIAL_CONTRACT_TYPES
}


def _contract_from_data(root: dict[str, object]) -> FinancialContract:
    if root.get("contract_version") != FINANCIAL_CONTRACT_VERSION:
        raise FinancialContractSerializationError("unsupported financial contract version")
    name = root.get("contract_type")
    cls = _CONTRACT_TYPES.get(cast(str, name))
    if cls is None:
        raise FinancialContractSerializationError("unknown financial contract type")
    raw_fields = _object(root.get("fields"), "fields")
    expected = {item.name for item in fields(cls)}
    if set(raw_fields) != expected:
        raise FinancialContractSerializationError("financial contract fields do not match schema")
    values: dict[str, object] = {}
    for field_name, raw in raw_fields.items():
        enum_type = _ENUM_FIELDS.get((cast(str, name), field_name))
        values[field_name] = enum_type(cast(str, raw)) if enum_type else _decode(raw)
    try:
        return cast(FinancialContract, cls(**values))
    except (DomainInvariantError, TypeError, ValueError) as exc:
        raise FinancialContractSerializationError("invalid financial contract value") from exc


def deserialize_financial_contract(payload: bytes) -> FinancialContract:
    """Decode canonical bytes and reject alternate/non-canonical encodings."""
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FinancialContractSerializationError("invalid financial contract JSON") from exc
    root = _object(raw, "financial contract")
    value = _contract_from_data(root)
    if serialize_financial_contract(value) != payload:
        raise FinancialContractSerializationError("financial contract JSON is not canonical")
    return value
