"""Immutable provider-neutral Market Data contracts (MD-001 / ASA-ARCH-007)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, TypeAlias, cast

from domain.financial import (
    EarningsEvent,
    ExpirationCollection,
    ExpirationCycle,
    FinancialContract,
    IndexSettlementValue,
    OptionChain,
    OptionContract,
    deserialize_financial_contract,
    financial_contract_to_data,
)
from domain.historical_options import HistoricalOptionPanel, HistoricalOptionSnapshot
from domain.operational import (
    CanonicalInstrumentIdentity,
    Instrument,
    InstrumentKind,
    SectorClassification,
)
from domain.references import EvidenceKind, EvidenceReference
from domain.values import DomainInvariantError, require_finite_decimal, require_tz_aware

MARKET_DATA_CONTRACT_VERSION = "v1"


def _text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise DomainInvariantError(f"{owner}.{field_name} must be non-empty normalized text")


def _decimal(
    value: Decimal | None,
    owner: str,
    field_name: str,
    *,
    positive: bool = False,
) -> None:
    if value is None:
        return
    require_finite_decimal(value, owner, field_name)
    if value < 0 or (positive and value == 0):
        qualifier = "positive" if positive else "non-negative"
        raise DomainInvariantError(f"{owner}.{field_name} must be {qualifier}")


def _canonical_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _utc(value: datetime) -> datetime:
    require_tz_aware(value, "MarketData", "datetime")
    return value.astimezone(UTC)


class MarketCapability(str, Enum):
    REAL_TIME_QUOTE_V1 = "real_time_quote_v1"
    HISTORICAL_BARS_V1 = "historical_bars_v1"
    OPTION_CHAIN_V1 = "option_chain_v1"
    EARNINGS_CALENDAR_V1 = "earnings_calendar_v1"
    TRADING_CALENDAR_V1 = "trading_calendar_v1"
    CORPORATE_ACTIONS_V1 = "corporate_actions_v1"
    # X01 (SP-01A): exchange-published index settlement values (SOQ). A
    # canonical fact; never derived from quotes, futures or ETFs.
    INDEX_SETTLEMENT_VALUE_V1 = "index_settlement_value_v1"
    # X04 (SP-01B): provider-neutral published rate observations (Treasury
    # bill rates, risk-free and dividend-yield series).
    RATE_OBSERVATION_V1 = "rate_observation_v1"
    # X05 (SP-01C): provider-neutral option trade prints. Quotes, marks and
    # midpoint observations are deliberately separate capabilities.
    OPTION_TRADE_TAPE_V1 = "option_trade_tape_v1"
    # X07 (SP-01D): published index-level dividend points. Constituent
    # corporate actions are not an equivalent source for this capability.
    INDEX_DIVIDEND_POINTS_V1 = "index_dividend_points_v1"
    # Point-in-time security classification and shares outstanding.
    SECURITY_MASTER_V1 = "security_master_v1"
    # A08 (SP-05B): sealed point-in-time option observations. No provider is
    # implied; absent authoritative history remains typed UNKNOWN.
    HISTORICAL_OPTION_PANEL_V1 = "historical_option_panel_v1"


class MarketDataSubjectType(str, Enum):
    INSTRUMENT = "instrument"
    OPTION_UNDERLYING = "option_underlying"
    EARNINGS_SECURITY = "earnings_security"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    DELAYED = "delayed"
    PRIOR_SESSION = "prior_session"
    STALE = "stale"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class AdjustedCloseBasis(str, Enum):  # noqa: UP042 -- preserve sibling contract enum style
    """Corporate-action basis of an explicitly supplied adjusted close."""

    SPLIT_ADJUSTED = "split_adjusted"
    SPLIT_AND_DIVIDEND_ADJUSTED = "split_and_dividend_adjusted"


class ProviderErrorKind(str, Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    SCHEMA = "schema"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class TradingCalendarEventType(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    EARLY_CLOSE = "early_close"
    HALT = "halt"
    HOLIDAY = "holiday"


class CorporateActionType(str, Enum):
    DIVIDEND = "dividend"
    SPLIT = "split"
    MERGER = "merger"
    SPINOFF = "spinoff"
    OTHER = "other"


class CorporateActionStatus(str, Enum):
    ANNOUNCED = "announced"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


def _evidence(values: tuple[EvidenceReference, ...], owner: str) -> tuple[EvidenceReference, ...]:
    if not values or not all(isinstance(value, EvidenceReference) for value in values):
        raise DomainInvariantError(f"{owner}.evidence requires EvidenceReference values")
    normalized = tuple(
        sorted(
            values, key=lambda value: (value.kind.value, value.referenced_id, value.version or 0)
        )
    )
    if len(normalized) != len(set(normalized)):
        raise DomainInvariantError(f"{owner}.evidence contains duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class ProviderAddressProjection:
    provider_id: str
    projection_schema_version: str
    address_type: str
    address_value: str
    effective_from: datetime
    effective_until: datetime | None
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        for name in ("provider_id", "projection_schema_version", "address_type", "address_value"):
            _text(getattr(self, name), "ProviderAddressProjection", name)
        require_tz_aware(self.effective_from, "ProviderAddressProjection", "effective_from")
        if self.effective_until is not None:
            require_tz_aware(self.effective_until, "ProviderAddressProjection", "effective_until")
            if self.effective_until <= self.effective_from:
                raise DomainInvariantError("ProviderAddressProjection validity window is empty")
        forbidden = ("://", "authorization", "password", "token", "cookie")
        if any(value in self.address_value.lower() for value in forbidden):
            raise DomainInvariantError("ProviderAddressProjection address must be credential-free")
        object.__setattr__(self, "evidence", _evidence(self.evidence, "ProviderAddressProjection"))

    @property
    def projection_identity(self) -> str:
        return _content_identity("asa.provider_address_projection", self)


@dataclass(frozen=True, slots=True)
class MarketDataRequestContext:
    semantic_start: datetime
    semantic_end: datetime
    required_fields: tuple[str, ...]
    provider_address_projections: tuple[ProviderAddressProjection, ...]
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        require_tz_aware(self.semantic_start, "MarketDataRequestContext", "semantic_start")
        require_tz_aware(self.semantic_end, "MarketDataRequestContext", "semantic_end")
        if self.semantic_start > self.semantic_end:
            raise DomainInvariantError("MarketDataRequestContext time window is inverted")
        required = tuple(sorted(set(self.required_fields)))
        if not required or any(not value or value != value.strip() for value in required):
            raise DomainInvariantError("MarketDataRequestContext requires normalized fields")
        projections = tuple(
            sorted(
                self.provider_address_projections,
                key=lambda value: (
                    value.provider_id,
                    value.projection_schema_version,
                    value.address_type,
                    value.effective_from,
                    value.projection_identity,
                ),
            )
        )
        if len(projections) != len(set(projections)):
            raise DomainInvariantError("MarketDataRequestContext contains duplicate projections")
        object.__setattr__(self, "required_fields", required)
        object.__setattr__(self, "provider_address_projections", projections)
        object.__setattr__(self, "evidence", _evidence(self.evidence, "MarketDataRequestContext"))


@dataclass(frozen=True, slots=True)
class MarketDataSubject:
    canonical_instrument: Instrument
    subject_type: MarketDataSubjectType
    requested_capability: MarketCapability
    request_context: MarketDataRequestContext

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_instrument, Instrument):
            raise DomainInvariantError("MarketDataSubject requires a canonical Instrument")
        if not isinstance(self.subject_type, MarketDataSubjectType):
            raise DomainInvariantError("MarketDataSubject subject_type is invalid")
        expected_type = {
            MarketCapability.REAL_TIME_QUOTE_V1: MarketDataSubjectType.INSTRUMENT,
            MarketCapability.HISTORICAL_BARS_V1: MarketDataSubjectType.INSTRUMENT,
            MarketCapability.OPTION_CHAIN_V1: MarketDataSubjectType.OPTION_UNDERLYING,
            MarketCapability.EARNINGS_CALENDAR_V1: MarketDataSubjectType.EARNINGS_SECURITY,
            MarketCapability.INDEX_SETTLEMENT_VALUE_V1: MarketDataSubjectType.INSTRUMENT,
            MarketCapability.RATE_OBSERVATION_V1: MarketDataSubjectType.INSTRUMENT,
            MarketCapability.OPTION_TRADE_TAPE_V1: MarketDataSubjectType.OPTION_UNDERLYING,
            MarketCapability.INDEX_DIVIDEND_POINTS_V1: MarketDataSubjectType.INSTRUMENT,
            MarketCapability.SECURITY_MASTER_V1: MarketDataSubjectType.INSTRUMENT,
            MarketCapability.HISTORICAL_OPTION_PANEL_V1: MarketDataSubjectType.OPTION_UNDERLYING,
        }.get(self.requested_capability)
        if expected_type is not None and self.subject_type is not expected_type:
            raise DomainInvariantError("MarketDataSubject subject type does not match capability")

    @property
    def subject_identity(self) -> str:
        return _content_identity("asa.market_data_subject", self)

    def projection_for(
        self, provider_id: str, address_type: str, at: datetime
    ) -> ProviderAddressProjection:
        require_tz_aware(at, "MarketDataSubject", "projection_time")
        matches = tuple(
            projection
            for projection in self.request_context.provider_address_projections
            if projection.provider_id == provider_id
            and projection.address_type == address_type
            and projection.effective_from <= at
            and (projection.effective_until is None or at < projection.effective_until)
        )
        if len(matches) != 1:
            raise DomainInvariantError(
                "MarketDataSubject requires one effective provider projection"
            )
        return matches[0]


@dataclass(frozen=True, slots=True)
class Quote:
    instrument: Instrument
    bid: Decimal | None
    ask: Decimal | None
    last: Decimal | None
    bid_size: Decimal | None
    ask_size: Decimal | None
    volume: Decimal | None
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("Quote.instrument must be an Instrument")
        _text(self.currency, "Quote", "currency")
        if self.currency != self.instrument.currency:
            raise DomainInvariantError("Quote.currency must match Instrument.currency")
        if self.bid is None and self.ask is None and self.last is None:
            raise DomainInvariantError("Quote requires at least one price")
        for name in ("bid", "ask", "last", "bid_size", "ask_size", "volume"):
            _decimal(getattr(self, name), "Quote", name)
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise DomainInvariantError("Quote bid cannot exceed ask")


class RateBasis(str, Enum):  # noqa: UP042 -- preserve sibling contract enum style
    """X04: the quoting convention of a published rate. Bases are never mixed."""

    BANK_DISCOUNT = "bank_discount"
    COUPON_EQUIVALENT = "coupon_equivalent"
    DIVIDEND_YIELD = "dividend_yield"


@dataclass(frozen=True, slots=True)
class RateObservation:
    """X04 (SP-01B): one published value of a rate series.

    ``value`` is a decimal fraction (3.69% -> 0.0369). ``effective_date`` is
    the publication date the value applies to; ``tenor_days`` is the
    instrument tenor the series quotes, when it has one.
    """

    instrument: Instrument
    basis: RateBasis
    tenor_days: int | None
    value: Decimal
    effective_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("RateObservation.instrument must be an Instrument")
        if self.instrument.kind is not InstrumentKind.RATE:
            raise DomainInvariantError("RateObservation.instrument must be a RATE series")
        if not isinstance(self.basis, RateBasis):
            raise DomainInvariantError("RateObservation.basis must be a RateBasis")
        if self.tenor_days is not None and (
            type(self.tenor_days) is not int or self.tenor_days <= 0
        ):
            raise DomainInvariantError("RateObservation.tenor_days must be a positive integer")
        if not isinstance(self.value, Decimal):
            raise DomainInvariantError("RateObservation.value is required")
        _decimal(self.value, "RateObservation", "value")
        if abs(self.value) >= 1:
            raise DomainInvariantError("RateObservation.value must be a decimal fraction")
        if not isinstance(self.effective_date, date) or isinstance(self.effective_date, datetime):
            raise DomainInvariantError("RateObservation.effective_date must be a date")


@dataclass(frozen=True, slots=True)
class OptionTrade:
    """X05: one immutable provider-neutral option trade print."""

    source_trade_id: str
    contract_identity: str
    price: Decimal
    size: Decimal
    event_time: datetime
    observed_time: datetime
    sale_condition_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.source_trade_id, "OptionTrade", "source_trade_id")
        _text(self.contract_identity, "OptionTrade", "contract_identity")
        _decimal(self.price, "OptionTrade", "price", positive=True)
        _decimal(self.size, "OptionTrade", "size", positive=True)
        require_tz_aware(self.event_time, "OptionTrade", "event_time")
        require_tz_aware(self.observed_time, "OptionTrade", "observed_time")
        if self.observed_time < self.event_time:
            raise DomainInvariantError("OptionTrade observed_time cannot precede event_time")
        codes = tuple(sorted(set(self.sale_condition_codes)))
        if any(not code or code != code.strip() for code in codes):
            raise DomainInvariantError("OptionTrade sale condition codes must be normalized")
        object.__setattr__(self, "sale_condition_codes", codes)

    @property
    def identity(self) -> str:
        return _content_identity("asa.option_trade", self)


@dataclass(frozen=True, slots=True)
class OptionTradeTape:
    """X05: exact prints for one option contract, ordered by event time."""

    contract_identity: str
    as_of: datetime
    trades: tuple[OptionTrade, ...]

    def __post_init__(self) -> None:
        _text(self.contract_identity, "OptionTradeTape", "contract_identity")
        require_tz_aware(self.as_of, "OptionTradeTape", "as_of")
        ordered = tuple(
            sorted(
                self.trades,
                key=lambda trade: (trade.event_time, trade.observed_time, trade.identity),
            )
        )
        if any(trade.contract_identity != self.contract_identity for trade in ordered):
            raise DomainInvariantError("OptionTradeTape trades must share contract identity")
        if any(trade.observed_time > self.as_of for trade in ordered):
            raise DomainInvariantError("OptionTradeTape as_of precedes an observed trade")
        identities = tuple(trade.identity for trade in ordered)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("OptionTradeTape contains duplicate trades")
        object.__setattr__(self, "trades", ordered)


@dataclass(frozen=True, slots=True)
class IndexDividendPoints:
    """X07: published dividends for an index, denominated in index points."""

    instrument: Instrument
    points: Decimal
    effective_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("IndexDividendPoints.instrument must be an Instrument")
        if self.instrument.kind is not InstrumentKind.INDEX:
            raise DomainInvariantError("IndexDividendPoints.instrument must be an INDEX")
        _decimal(self.points, "IndexDividendPoints", "points")
        if not isinstance(self.effective_date, date) or isinstance(self.effective_date, datetime):
            raise DomainInvariantError("IndexDividendPoints.effective_date must be a date")


class SecurityType(str, Enum):  # noqa: UP042 -- canonical external classification
    COMMON_STOCK = "common_stock"
    PREFERRED_STOCK = "preferred_stock"
    ETF = "etf"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SecurityMasterRecord:
    """Point-in-time canonical security classification and capitalization input."""

    instrument: Instrument
    security_type: SecurityType
    shares_outstanding: Decimal
    effective_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("SecurityMasterRecord.instrument must be an Instrument")
        if self.instrument.kind is not InstrumentKind.EQUITY:
            raise DomainInvariantError("SecurityMasterRecord.instrument must be an EQUITY")
        if not isinstance(self.security_type, SecurityType):
            raise DomainInvariantError("SecurityMasterRecord.security_type must be a SecurityType")
        _decimal(
            self.shares_outstanding,
            "SecurityMasterRecord",
            "shares_outstanding",
            positive=True,
        )
        if not isinstance(self.effective_date, date) or isinstance(self.effective_date, datetime):
            raise DomainInvariantError("SecurityMasterRecord.effective_date must be a date")


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    instrument: Instrument
    interval_seconds: int
    start_at: datetime
    end_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    adjusted_close: Decimal | None = None
    adjusted_close_basis: AdjustedCloseBasis | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("OHLCVBar.instrument must be an Instrument")
        if type(self.interval_seconds) is not int or self.interval_seconds <= 0:
            raise DomainInvariantError("OHLCVBar.interval_seconds must be a positive integer")
        require_tz_aware(self.start_at, "OHLCVBar", "start_at")
        require_tz_aware(self.end_at, "OHLCVBar", "end_at")
        if self.start_at >= self.end_at:
            raise DomainInvariantError("OHLCVBar start_at must precede end_at")
        if Decimal(str((self.end_at - self.start_at).total_seconds())) != Decimal(
            self.interval_seconds
        ):
            raise DomainInvariantError("OHLCVBar interval must match its time window")
        for name in ("open", "high", "low", "close", "volume"):
            _decimal(getattr(self, name), "OHLCVBar", name)
        _decimal(self.adjusted_close, "OHLCVBar", "adjusted_close", positive=True)
        if (self.adjusted_close is None) != (self.adjusted_close_basis is None):
            raise DomainInvariantError(
                "OHLCVBar adjusted_close and adjusted_close_basis must be supplied together"
            )
        if self.high < max(self.open, self.close, self.low):
            raise DomainInvariantError("OHLCVBar high is incoherent")
        if self.low > min(self.open, self.close, self.high):
            raise DomainInvariantError("OHLCVBar low is incoherent")


@dataclass(frozen=True, slots=True)
class OHLCVSeries:
    """The provider-neutral collection value for HISTORICAL_BARS_V1
    (SPRINT-014 S14-PR-05A, Founder-approved bounded contract extension):
    one logical historical-bars acquisition request legitimately produces
    many bars (one per trading day in the requested window), but the
    generic subject planner and ObservationResolver both assume at most
    one observation per provider per capability. Bundling every bar into
    one OHLCVSeries value -- the same technique domain.financial.
    ExpirationCollection already establishes for OPTION_CHAIN_V1's own
    expirations-only response -- keeps that invariant intact: one
    CapabilityRequest still resolves to exactly one MarketObservation.

    Mirrors ExpirationCollection's own shape: a shared subject-level
    identity (here, ``instrument``/``interval_seconds``) plus an ordered,
    deduplicated collection of the same per-item value type
    (domain.market_data.OHLCVBar) this capability already carries one of.
    """

    instrument: Instrument
    interval_seconds: int
    as_of: datetime
    bars: tuple[OHLCVBar, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("OHLCVSeries.instrument must be an Instrument")
        if type(self.interval_seconds) is not int or self.interval_seconds <= 0:
            raise DomainInvariantError("OHLCVSeries.interval_seconds must be a positive integer")
        require_tz_aware(self.as_of, "OHLCVSeries", "as_of")
        if not self.bars:
            raise DomainInvariantError("OHLCVSeries requires at least one bar")
        if not all(isinstance(item, OHLCVBar) for item in self.bars):
            raise DomainInvariantError("OHLCVSeries must contain OHLCVBar records")
        normalized = tuple(sorted(self.bars, key=lambda item: item.start_at))
        if any(item.instrument.identity != self.instrument.identity for item in normalized):
            raise DomainInvariantError("OHLCVSeries bars must share the series instrument")
        if any(item.interval_seconds != self.interval_seconds for item in normalized):
            raise DomainInvariantError("OHLCVSeries bars must share interval_seconds")
        if any(item.end_at > self.as_of for item in normalized):
            raise DomainInvariantError("OHLCVSeries as_of precedes an included bar")
        start_times = tuple(item.start_at for item in normalized)
        if len(start_times) != len(set(start_times)):
            raise DomainInvariantError("OHLCVSeries contains duplicate bar start_at values")
        object.__setattr__(self, "bars", normalized)


@dataclass(frozen=True, slots=True)
class TradingCalendarEvent:
    venue: str
    event_type: TradingCalendarEventType
    starts_at: datetime
    ends_at: datetime
    trading_date: date

    def __post_init__(self) -> None:
        _text(self.venue, "TradingCalendarEvent", "venue")
        if not isinstance(self.trading_date, date):
            raise DomainInvariantError("TradingCalendarEvent.trading_date must be a date")
        require_tz_aware(self.starts_at, "TradingCalendarEvent", "starts_at")
        require_tz_aware(self.ends_at, "TradingCalendarEvent", "ends_at")
        if self.starts_at > self.ends_at:
            raise DomainInvariantError("TradingCalendarEvent starts_at cannot follow ends_at")


@dataclass(frozen=True, slots=True)
class CorporateActionPlaceholder:
    instrument: Instrument
    action_type: CorporateActionType
    effective_date: date
    status: CorporateActionStatus
    external_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, Instrument):
            raise DomainInvariantError("CorporateActionPlaceholder.instrument must be Instrument")
        if not isinstance(self.effective_date, date):
            raise DomainInvariantError("CorporateActionPlaceholder.effective_date must be a date")
        if self.external_reference is not None:
            _text(
                self.external_reference,
                "CorporateActionPlaceholder",
                "external_reference",
            )


@dataclass(frozen=True, slots=True)
class FreshnessMetadata:
    as_of: datetime
    effective_time: datetime
    threshold_seconds: int
    age_seconds: int
    status: FreshnessStatus

    def __post_init__(self) -> None:
        require_tz_aware(self.as_of, "FreshnessMetadata", "as_of")
        require_tz_aware(self.effective_time, "FreshnessMetadata", "effective_time")
        if type(self.threshold_seconds) is not int or self.threshold_seconds < 0:
            raise DomainInvariantError("FreshnessMetadata.threshold_seconds must be non-negative")
        if type(self.age_seconds) is not int or self.age_seconds < 0:
            raise DomainInvariantError("FreshnessMetadata.age_seconds must be non-negative")
        expected_age = max(0, int((self.as_of - self.effective_time).total_seconds()))
        if self.age_seconds != expected_age:
            raise DomainInvariantError("FreshnessMetadata.age_seconds must match semantic times")
        if self.status is FreshnessStatus.FRESH and self.age_seconds > self.threshold_seconds:
            raise DomainInvariantError("stale evidence cannot report freshness status fresh")
        if self.status is FreshnessStatus.STALE and self.age_seconds <= self.threshold_seconds:
            raise DomainInvariantError("fresh evidence cannot report freshness status stale")
        if (
            self.status is FreshnessStatus.PRIOR_SESSION
            and self.age_seconds <= self.threshold_seconds
        ):
            raise DomainInvariantError("recent evidence cannot report prior-session freshness")


@dataclass(frozen=True, slots=True)
class CompletenessMetadata:
    required_fields: tuple[str, ...]
    present_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        required = tuple(sorted(set(self.required_fields)))
        present = tuple(sorted(set(self.present_fields)))
        missing = tuple(sorted(set(self.missing_fields)))
        if not required:
            raise DomainInvariantError("CompletenessMetadata requires required_fields")
        if any(not value or value != value.strip() for value in (*required, *present, *missing)):
            raise DomainInvariantError("CompletenessMetadata fields must be normalized text")
        if set(missing) != set(required) - set(present):
            raise DomainInvariantError("CompletenessMetadata.missing_fields is inconsistent")
        object.__setattr__(self, "required_fields", required)
        object.__setattr__(self, "present_fields", present)
        object.__setattr__(self, "missing_fields", missing)


@dataclass(frozen=True, slots=True)
class ProviderProvenance:
    provider_id: str
    provider_request_reference: str
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        _text(self.provider_id, "ProviderProvenance", "provider_id")
        _text(
            self.provider_request_reference,
            "ProviderProvenance",
            "provider_request_reference",
        )
        if not self.evidence or not all(
            isinstance(value, EvidenceReference) for value in self.evidence
        ):
            raise DomainInvariantError("ProviderProvenance requires EvidenceReference values")


@dataclass(frozen=True, slots=True)
class NormalizedProviderErrorMetadata:
    kind: ProviderErrorKind
    code: str
    retryable: bool
    safe_summary: str

    def __post_init__(self) -> None:
        _text(self.code, "NormalizedProviderErrorMetadata", "code")
        _text(self.safe_summary, "NormalizedProviderErrorMetadata", "safe_summary")
        if type(self.retryable) is not bool:
            raise DomainInvariantError("NormalizedProviderErrorMetadata.retryable must be bool")


MarketObservationValue: TypeAlias = (
    Quote
    | OHLCVBar
    | OHLCVSeries
    | OptionContract
    | OptionChain
    | ExpirationCycle
    | ExpirationCollection
    | EarningsEvent
    | TradingCalendarEvent
    | CorporateActionPlaceholder
    | IndexSettlementValue
    | RateObservation
    | OptionTradeTape
    | IndexDividendPoints
    | SecurityMasterRecord
    | HistoricalOptionPanel
)


@dataclass(frozen=True, slots=True)
class MarketObservation:
    observation_id: str
    capability: MarketCapability
    subject: MarketDataSubject
    effective_time: datetime
    recorded_time: datetime
    value: MarketObservationValue
    schema_version: str
    provenance: ProviderProvenance
    freshness: FreshnessMetadata
    completeness: CompletenessMetadata

    def __post_init__(self) -> None:
        _text(self.observation_id, "MarketObservation", "observation_id")
        _text(self.schema_version, "MarketObservation", "schema_version")
        require_tz_aware(self.effective_time, "MarketObservation", "effective_time")
        require_tz_aware(self.recorded_time, "MarketObservation", "recorded_time")
        if self.freshness.effective_time != self.effective_time:
            raise DomainInvariantError("MarketObservation freshness effective_time mismatch")
        if self.subject.requested_capability is not self.capability:
            raise DomainInvariantError("MarketObservation subject capability mismatch")
        expected_capability = {
            Quote: MarketCapability.REAL_TIME_QUOTE_V1,
            OHLCVBar: MarketCapability.HISTORICAL_BARS_V1,
            OHLCVSeries: MarketCapability.HISTORICAL_BARS_V1,
            OptionContract: MarketCapability.OPTION_CHAIN_V1,
            OptionChain: MarketCapability.OPTION_CHAIN_V1,
            ExpirationCycle: MarketCapability.OPTION_CHAIN_V1,
            ExpirationCollection: MarketCapability.OPTION_CHAIN_V1,
            EarningsEvent: MarketCapability.EARNINGS_CALENDAR_V1,
            TradingCalendarEvent: MarketCapability.TRADING_CALENDAR_V1,
            CorporateActionPlaceholder: MarketCapability.CORPORATE_ACTIONS_V1,
            IndexSettlementValue: MarketCapability.INDEX_SETTLEMENT_VALUE_V1,
            RateObservation: MarketCapability.RATE_OBSERVATION_V1,
            OptionTradeTape: MarketCapability.OPTION_TRADE_TAPE_V1,
            IndexDividendPoints: MarketCapability.INDEX_DIVIDEND_POINTS_V1,
            SecurityMasterRecord: MarketCapability.SECURITY_MASTER_V1,
            HistoricalOptionPanel: MarketCapability.HISTORICAL_OPTION_PANEL_V1,
        }.get(type(self.value))
        if expected_capability is not self.capability:
            raise DomainInvariantError("MarketObservation value does not match capability")
        if isinstance(self.value, (IndexDividendPoints, SecurityMasterRecord)) and (
            self.value.instrument != self.subject.canonical_instrument
        ):
            raise DomainInvariantError(
                "MarketObservation value instrument does not match canonical subject"
            )
        if isinstance(self.value, HistoricalOptionPanel) and (
            self.value.subject != self.subject.canonical_instrument
        ):
            raise DomainInvariantError("MarketObservation historical option panel subject mismatch")
        expected = market_observation_identity(
            self.provenance.provider_id,
            self.capability,
            self.subject,
            self.effective_time,
            self.value,
            self.schema_version,
        )
        if self.observation_id != expected:
            raise DomainInvariantError("MarketObservation.observation_id is not content-derived")


MarketDataContract: TypeAlias = (
    Quote
    | RateObservation
    | OptionTrade
    | OptionTradeTape
    | IndexDividendPoints
    | SecurityMasterRecord
    | OHLCVBar
    | OHLCVSeries
    | TradingCalendarEvent
    | CorporateActionPlaceholder
    | FreshnessMetadata
    | CompletenessMetadata
    | ProviderProvenance
    | NormalizedProviderErrorMetadata
    | ProviderAddressProjection
    | MarketDataRequestContext
    | MarketDataSubject
    | MarketObservation
    | HistoricalOptionSnapshot
    | HistoricalOptionPanel
)

_MARKET_TYPES = {
    value.__name__: value
    for value in (
        Quote,
        RateObservation,
        OptionTrade,
        OptionTradeTape,
        IndexDividendPoints,
        SecurityMasterRecord,
        OHLCVBar,
        OHLCVSeries,
        TradingCalendarEvent,
        CorporateActionPlaceholder,
        FreshnessMetadata,
        CompletenessMetadata,
        ProviderProvenance,
        NormalizedProviderErrorMetadata,
        ProviderAddressProjection,
        MarketDataRequestContext,
        MarketDataSubject,
        MarketObservation,
        HistoricalOptionSnapshot,
        HistoricalOptionPanel,
    )
}
_ENUM_TYPES = {
    value.__name__: value
    for value in (
        MarketCapability,
        AdjustedCloseBasis,
        RateBasis,
        SecurityType,
        FreshnessStatus,
        ProviderErrorKind,
        TradingCalendarEventType,
        CorporateActionType,
        CorporateActionStatus,
        MarketDataSubjectType,
    )
}


def _instrument_data(value: Instrument) -> dict[str, object]:
    return {
        "$instrument": {
            "identity": {
                "scheme": value.identity.scheme,
                "value": value.identity.value,
            },
            "kind": value.kind.value,
            "display_symbol": value.display_symbol,
            "currency": value.currency,
            "sector": None
            if value.sector is None
            else {
                "taxonomy": value.sector.taxonomy,
                "taxonomy_version": value.sector.taxonomy_version,
                "code": value.sector.code,
            },
            "underlying_identity": None
            if value.underlying_identity is None
            else {
                "scheme": value.underlying_identity.scheme,
                "value": value.underlying_identity.value,
            },
        }
    }


def _wire(value: object) -> object:
    if isinstance(value, Decimal):
        return {"$decimal": _canonical_decimal(value)}
    if isinstance(value, datetime):
        return {"$instant": _utc(value).isoformat().replace("+00:00", "Z")}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if isinstance(value, Enum):
        return {"$enum": [type(value).__name__, value.value]}
    if isinstance(value, CanonicalInstrumentIdentity):
        return {"$canonical_instrument_identity": [value.scheme, value.value]}
    if isinstance(value, Instrument):
        return _instrument_data(value)
    if isinstance(value, EvidenceReference):
        return {
            "$evidence": [value.kind.value, value.referenced_id, value.version],
        }
    if isinstance(value, tuple):
        return [_wire(item) for item in value]
    if isinstance(
        value,
        (
            OptionContract,
            OptionChain,
            ExpirationCycle,
            ExpirationCollection,
            EarningsEvent,
            IndexSettlementValue,
        ),
    ):
        return {"$financial_contract": financial_contract_to_data(cast(FinancialContract, value))}
    if type(value).__name__ in _MARKET_TYPES:
        return market_data_to_data(cast(MarketDataContract, value))
    return value


def market_data_to_data(value: MarketDataContract) -> dict[str, object]:
    return {
        "contract_type": type(value).__name__,
        "contract_version": MARKET_DATA_CONTRACT_VERSION,
        "fields": {item.name: _wire(getattr(value, item.name)) for item in fields(value)},
    }


def serialize_market_data(value: MarketDataContract) -> bytes:
    return json.dumps(
        market_data_to_data(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _decode_instrument(value: object) -> Instrument:
    item = cast(dict[str, Any], value)
    identity = cast(dict[str, str], item["identity"])
    underlying = cast(dict[str, str] | None, item["underlying_identity"])
    sector_data = cast(dict[str, str] | None, item["sector"])
    return Instrument(
        CanonicalInstrumentIdentity(identity["scheme"], identity["value"]),
        InstrumentKind(cast(str, item["kind"])),
        cast(str, item["display_symbol"]),
        cast(str, item["currency"]),
        None
        if sector_data is None
        else SectorClassification(
            sector_data["taxonomy"], sector_data["taxonomy_version"], sector_data["code"]
        ),
        None
        if underlying is None
        else CanonicalInstrumentIdentity(underlying["scheme"], underlying["value"]),
    )


def _decode(value: object) -> object:
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    if not isinstance(value, dict):
        return value
    item = cast(dict[str, Any], value)
    if set(item) == {"$decimal"}:
        try:
            return Decimal(cast(str, item["$decimal"]))
        except (InvalidOperation, TypeError) as exc:
            raise DomainInvariantError("invalid serialized Decimal") from exc
    if set(item) == {"$instant"}:
        return datetime.fromisoformat(cast(str, item["$instant"]).replace("Z", "+00:00"))
    if set(item) == {"$date"}:
        return date.fromisoformat(cast(str, item["$date"]))
    if set(item) == {"$enum"}:
        enum_name, member = cast(list[str], item["$enum"])
        return _ENUM_TYPES[enum_name](member)
    if set(item) == {"$canonical_instrument_identity"}:
        scheme, identity = cast(list[str], item["$canonical_instrument_identity"])
        return CanonicalInstrumentIdentity(scheme, identity)
    if set(item) == {"$instrument"}:
        return _decode_instrument(item["$instrument"])
    if set(item) == {"$evidence"}:
        kind, referenced_id, version = cast(list[Any], item["$evidence"])
        return EvidenceReference(EvidenceKind(kind), referenced_id, version)
    if set(item) == {"$financial_contract"}:
        payload = json.dumps(
            item["$financial_contract"], sort_keys=True, separators=(",", ":")
        ).encode()
        return deserialize_financial_contract(payload)
    return _decode_contract(item)


def _decode_contract(value: dict[str, Any]) -> MarketDataContract:
    if value.get("contract_version") != MARKET_DATA_CONTRACT_VERSION:
        raise DomainInvariantError("unsupported Market Data contract version")
    type_name = value.get("contract_type")
    if not isinstance(type_name, str) or type_name not in _MARKET_TYPES:
        raise DomainInvariantError("unknown Market Data contract type")
    raw_fields = value.get("fields")
    if not isinstance(raw_fields, dict):
        raise DomainInvariantError("Market Data contract fields must be an object")
    decoded = {name: _decode(item) for name, item in raw_fields.items()}
    try:
        constructor = cast(Any, _MARKET_TYPES[type_name])
        return cast(MarketDataContract, constructor(**decoded))
    except TypeError as exc:
        raise DomainInvariantError("invalid Market Data contract fields") from exc


def deserialize_market_data(payload: bytes) -> MarketDataContract:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainInvariantError("invalid Market Data serialization") from exc
    if not isinstance(value, dict):
        raise DomainInvariantError("Market Data serialization must be an object")
    return _decode_contract(cast(dict[str, Any], value))


def market_observation_identity(
    provider_id: str,
    capability: MarketCapability,
    subject: MarketDataSubject,
    effective_time: datetime,
    value: MarketObservationValue,
    schema_version: str,
) -> str:
    _text(provider_id, "market_observation_identity", "provider_id")
    _text(schema_version, "market_observation_identity", "schema_version")
    require_tz_aware(effective_time, "market_observation_identity", "effective_time")
    payload = {
        "capability": capability.value,
        "effective_time": _utc(effective_time).isoformat().replace("+00:00", "Z"),
        "namespace": "asa.market_observation",
        "provider_id": provider_id,
        "schema_version": schema_version,
        "subject_identity": subject.subject_identity,
        "value": _wire(value),
        "version": MARKET_DATA_CONTRACT_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _content_identity(namespace: str, value: object) -> str:
    payload = {
        "identity_namespace": namespace,
        "identity_version": MARKET_DATA_CONTRACT_VERSION,
        "value": _wire(value),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
