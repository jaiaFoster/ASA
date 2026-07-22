"""Immutable provider-neutral Market Data contracts (MD-001 / ASA-ARCH-007)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, TypeAlias, cast

from domain.financial import (
    EarningsEvent,
    ExpirationCycle,
    FinancialContract,
    OptionChain,
    OptionContract,
    deserialize_financial_contract,
    financial_contract_to_data,
)
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
    return value.astimezone(timezone.utc)


class MarketCapability(str, Enum):
    REAL_TIME_QUOTE_V1 = "real_time_quote_v1"
    HISTORICAL_BARS_V1 = "historical_bars_v1"
    OPTION_CHAIN_V1 = "option_chain_v1"
    EARNINGS_CALENDAR_V1 = "earnings_calendar_v1"
    TRADING_CALENDAR_V1 = "trading_calendar_v1"
    CORPORATE_ACTIONS_V1 = "corporate_actions_v1"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


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
        if self.high < max(self.open, self.close, self.low):
            raise DomainInvariantError("OHLCVBar high is incoherent")
        if self.low > min(self.open, self.close, self.high):
            raise DomainInvariantError("OHLCVBar low is incoherent")


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
    | OptionContract
    | OptionChain
    | ExpirationCycle
    | EarningsEvent
    | TradingCalendarEvent
    | CorporateActionPlaceholder
)


@dataclass(frozen=True, slots=True)
class MarketObservation:
    observation_id: str
    capability: MarketCapability
    canonical_subject_id: CanonicalInstrumentIdentity
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
        expected_capability = {
            Quote: MarketCapability.REAL_TIME_QUOTE_V1,
            OHLCVBar: MarketCapability.HISTORICAL_BARS_V1,
            OptionContract: MarketCapability.OPTION_CHAIN_V1,
            OptionChain: MarketCapability.OPTION_CHAIN_V1,
            ExpirationCycle: MarketCapability.OPTION_CHAIN_V1,
            EarningsEvent: MarketCapability.EARNINGS_CALENDAR_V1,
            TradingCalendarEvent: MarketCapability.TRADING_CALENDAR_V1,
            CorporateActionPlaceholder: MarketCapability.CORPORATE_ACTIONS_V1,
        }.get(type(self.value))
        if expected_capability is not self.capability:
            raise DomainInvariantError("MarketObservation value does not match capability")
        expected = market_observation_identity(
            self.provenance.provider_id,
            self.capability,
            self.canonical_subject_id,
            self.effective_time,
            self.value,
            self.schema_version,
        )
        if self.observation_id != expected:
            raise DomainInvariantError("MarketObservation.observation_id is not content-derived")


MarketDataContract: TypeAlias = (
    Quote
    | OHLCVBar
    | TradingCalendarEvent
    | CorporateActionPlaceholder
    | FreshnessMetadata
    | CompletenessMetadata
    | ProviderProvenance
    | NormalizedProviderErrorMetadata
    | MarketObservation
)

_MARKET_TYPES = {
    value.__name__: value
    for value in (
        Quote,
        OHLCVBar,
        TradingCalendarEvent,
        CorporateActionPlaceholder,
        FreshnessMetadata,
        CompletenessMetadata,
        ProviderProvenance,
        NormalizedProviderErrorMetadata,
        MarketObservation,
    )
}
_ENUM_TYPES = {
    value.__name__: value
    for value in (
        MarketCapability,
        FreshnessStatus,
        ProviderErrorKind,
        TradingCalendarEventType,
        CorporateActionType,
        CorporateActionStatus,
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
    if isinstance(value, (OptionContract, OptionChain, ExpirationCycle, EarningsEvent)):
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
    canonical_subject_id: CanonicalInstrumentIdentity,
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
        "subject": [canonical_subject_id.scheme, canonical_subject_id.value],
        "value": _wire(value),
        "version": MARKET_DATA_CONTRACT_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
