"""Read-only Tradier Market Data adapter (MD-009)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import cast

from domain import (
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    ExpirationCycle,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataSubject,
    MarketObservation,
    OHLCVBar,
    OptionChain,
    OptionContract,
    OptionType,
    ProviderProvenance,
    Quote,
    Security,
    SecurityAssetType,
    market_observation_identity,
)
from domain.operational import CanonicalInstrumentIdentity
from domain.market_data import MarketObservationValue
from domain.values import DomainInvariantError
from market_data.config import ProviderConfig
from market_data.factory import ProviderDependencies, ProviderRegistration
from market_data.providers import (
    CapabilityRequest,
    HealthProbe,
    ProviderAttemptMetadata,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderHealthReport,
    ProviderIdentity,
    ProviderLimitDeclaration,
    ProviderMetadata,
    ProviderResponseMetadata,
    ProviderShutdownReport,
    ProviderStatus,
    ProviderValidationPlan,
    ProviderValidationReport,
    RequestBudgetAuthorization,
    ValidationCheckResult,
    ValidationCheckStatus,
    normalized_provider_error,
)
from market_data.transport import (
    ReadOnlyHttpRequest,
    ReadOnlyHttpResponse,
    ReadOnlyHttpTransport,
    ReadOnlyTransportError,
    ReadOnlyTransportTimeout,
)

TRADIER_CAPABILITIES = (
    MarketCapability.REAL_TIME_QUOTE_V1,
    MarketCapability.HISTORICAL_BARS_V1,
    MarketCapability.OPTION_CHAIN_V1,
)


class _EmptyPayload(ValueError):
    pass


class TradierProvider:
    """Official documented `/v1/markets` reads only; no account or order surface."""

    def __init__(self, config: ProviderConfig, dependencies: ProviderDependencies) -> None:
        if config.provider_id != "tradier" or config.credential is None:
            raise ValueError("Tradier requires its explicit enabled credential configuration")
        if not isinstance(dependencies.transport, ReadOnlyHttpTransport):
            raise ValueError("Tradier requires an injected read-only HTTP transport")
        self._config = config
        self._credential = config.credential
        self._dependencies = dependencies
        self._transport = dependencies.transport
        self._metadata = ProviderMetadata(
            ProviderIdentity("tradier", "tradier", config.adapter_version),
            TRADIER_CAPABILITIES,
            (
                ProviderLimitDeclaration("market_data_per_minute_production", "120", "documented"),
                ProviderLimitDeclaration("market_data_per_minute_sandbox", "60", "documented"),
            ),
            TRADIER_CAPABILITIES,
            "v1",
        )

    @property
    def provider_id(self) -> str:
        return "tradier"

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    @property
    def capabilities(self) -> tuple[MarketCapability, ...]:
        return self.metadata.capabilities

    def fetch(
        self, request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        if budget.provider_id != self.provider_id:
            raise DomainInvariantError("Tradier request budget provider mismatch")
        if request.capability not in self.capabilities:
            return self._failure(request, ProviderErrorCode.UNSUPPORTED_CAPABILITY, None, None)
        observations: list[MarketObservation] = []
        attempts: list[ProviderAttemptMetadata] = []
        for subject in request.subjects:
            projection = subject.projection_for("tradier", "symbol", request.effective_end)
            path, query, endpoint_class = self._endpoint(request, subject, projection.address_value)
            try:
                response = self._transport.get(
                    ReadOnlyHttpRequest(
                        self._config.endpoint_environment.value,
                        endpoint_class,
                        path,
                        query,
                        (
                            ("Accept", "application/json"),
                            ("Authorization", f"Bearer {self._credential.reveal()}"),
                        ),
                        self._config.timeout_seconds,
                    )
                )
            except ReadOnlyTransportTimeout:
                return self._failure(
                    request, ProviderErrorCode.TIMEOUT, None, tuple(attempts) or None
                )
            except ReadOnlyTransportError:
                return self._failure(
                    request, ProviderErrorCode.TRANSPORT_ERROR, None, tuple(attempts) or None
                )
            response_metadata = self._response_metadata(response)
            attempts.append(
                ProviderAttemptMetadata(
                    "tradier", request.capability, len(attempts) + 1, 1, response_metadata
                )
            )
            error_code = self._response_error(response)
            if error_code is not None:
                return self._failure(request, error_code, response, tuple(attempts))
            try:
                observations.extend(self._normalize(request, subject, response))
            except _EmptyPayload:
                return self._failure(
                    request, ProviderErrorCode.EMPTY_PAYLOAD, response, tuple(attempts)
                )
            except (KeyError, TypeError, ValueError, InvalidOperation, DomainInvariantError):
                return self._failure(
                    request, ProviderErrorCode.SCHEMA_MISMATCH, response, tuple(attempts)
                )
        if not observations:
            return self._failure(request, ProviderErrorCode.EMPTY_PAYLOAD, None, tuple(attempts))
        return ProviderFetchResult(tuple(observations), None, tuple(attempts))

    def health(self, probe: HealthProbe) -> ProviderHealthReport:
        return ProviderHealthReport(
            "tradier", ProviderStatus.UNKNOWN, probe.requested_at, "NOT_PROBED", None
        )

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport:
        started = self._dependencies.clock.now()
        checks: list[ValidationCheckResult] = []
        attempts: list[ProviderAttemptMetadata] = []
        subjects = {subject.requested_capability: subject for subject in plan.subjects}
        for capability in plan.capabilities:
            subject = subjects.get(capability)
            if subject is None:
                checks.append(
                    ValidationCheckResult(
                        capability.value,
                        ValidationCheckStatus.SKIPPED,
                        "INCONCLUSIVE",
                        "explicit validation subject was not supplied",
                    )
                )
                continue
            authorization = self._dependencies.budget_authorizer.authorize("tradier", capability, 1)
            context = subject.request_context
            result = self.fetch(
                CapabilityRequest(
                    capability,
                    (subject,),
                    context.semantic_start,
                    context.semantic_end,
                    context.required_fields,
                    300,
                ),
                authorization,
            )
            attempts.extend(result.attempts)
            checks.append(
                ValidationCheckResult(
                    capability.value,
                    ValidationCheckStatus.PASS
                    if result.error is None
                    else ValidationCheckStatus.FAIL,
                    "VALID_DATA" if result.error is None else result.error.code.value.upper(),
                    "bounded Tradier capability check completed",
                )
            )
        completed = self._dependencies.clock.now()
        report_id = hashlib.sha256(
            f"{plan.plan_id}:{started.isoformat()}:{completed.isoformat()}".encode()
        ).hexdigest()
        return ProviderValidationReport(
            report_id,
            plan.plan_id,
            "tradier",
            self._config.adapter_version,
            started,
            completed,
            tuple(checks),
            tuple(attempts),
        )

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport("tradier", self._dependencies.clock.now())

    def _endpoint(
        self, request: CapabilityRequest, subject: MarketDataSubject, symbol: str
    ) -> tuple[str, tuple[tuple[str, str], ...], str]:
        if request.capability is MarketCapability.REAL_TIME_QUOTE_V1:
            return "/v1/markets/quotes", (("greeks", "false"), ("symbols", symbol)), "quotes"
        if request.capability is MarketCapability.HISTORICAL_BARS_V1:
            return (
                "/v1/markets/history",
                (
                    ("end", request.effective_end.date().isoformat()),
                    ("interval", "daily"),
                    ("start", request.effective_start.date().isoformat()),
                    ("symbol", symbol),
                ),
                "history",
            )
        if "expirations" in request.required_fields and "contracts" not in request.required_fields:
            return (
                "/v1/markets/options/expirations",
                (("includeAllRoots", "false"), ("symbol", symbol)),
                "option_expirations",
            )
        expiration = subject.projection_for("tradier", "expiration", request.effective_end)
        return (
            "/v1/markets/options/chains",
            (("expiration", expiration.address_value), ("greeks", "true"), ("symbol", symbol)),
            "option_chain",
        )

    def _normalize(
        self, request: CapabilityRequest, subject: MarketDataSubject, response: ReadOnlyHttpResponse
    ) -> tuple[MarketObservation, ...]:
        if request.capability is MarketCapability.REAL_TIME_QUOTE_V1:
            rows = _rows(_mapping(response.json_body, "quotes").get("quote"))
            return tuple(
                self._observation(request, subject, _quote(subject, row), response, row)
                for row in rows
            )
        if request.capability is MarketCapability.HISTORICAL_BARS_V1:
            rows = _rows(_mapping(response.json_body, "history").get("day"))
            return tuple(
                self._observation(request, subject, _bar(subject, row), response, row)
                for row in rows
            )
        if "expirations" in request.required_fields and "contracts" not in request.required_fields:
            values = _mapping(response.json_body, "expirations").get("date")
            dates = values if isinstance(values, list) else [values]
            as_of = request.effective_end.date()
            return tuple(
                self._observation(
                    request,
                    subject,
                    ExpirationCycle(
                        parsed,
                        (parsed - as_of).days,
                        _is_monthly_expiration(parsed),
                        not _is_monthly_expiration(parsed),
                        as_of,
                        _evidence(response),
                    ),
                    response,
                    {},
                )
                for parsed in (_date(item) for item in dates)
            )
        rows = _rows(_mapping(response.json_body, "options").get("option"))
        chain = _chain(subject, rows, response, self._dependencies.clock.now())
        return (self._observation(request, subject, chain, response, rows[0] if rows else {}),)

    def _observation(
        self,
        request: CapabilityRequest,
        subject: MarketDataSubject,
        value: MarketObservationValue,
        response: ReadOnlyHttpResponse,
        row: Mapping[str, object],
    ) -> MarketObservation:
        received = self._dependencies.clock.now().astimezone(timezone.utc)
        if isinstance(value, OHLCVBar):
            effective = value.end_at
        elif isinstance(value, OptionChain):
            effective = value.observed_at
        else:
            effective = _observed_at(row, received)
        evidence = _evidence(response)
        present = tuple(field for field in request.required_fields if _field_present(field, value))
        missing = tuple(field for field in request.required_fields if field not in present)
        age = max(0, int((received - effective).total_seconds()))
        freshness = FreshnessMetadata(
            received,
            effective,
            request.maximum_age_seconds,
            age,
            FreshnessStatus.FRESH if age <= request.maximum_age_seconds else FreshnessStatus.STALE,
        )
        provenance = ProviderProvenance("tradier", response.request_reference, evidence)
        identity = market_observation_identity(
            "tradier", request.capability, subject, effective, value, "v1"
        )
        return MarketObservation(
            identity,
            request.capability,
            subject,
            effective,
            received,
            value,
            "v1",
            provenance,
            freshness,
            CompletenessMetadata(request.required_fields, present, missing),
        )

    def _response_metadata(self, response: ReadOnlyHttpResponse) -> ProviderResponseMetadata:
        quota = tuple(
            (key.lower(), value)
            for key, value in response.headers
            if key.lower().startswith("x-ratelimit-") and value
        )
        return ProviderResponseMetadata(
            "tradier",
            response.request_reference,
            self._dependencies.clock.now(),
            str(response.status_code),
            response.latency_milliseconds,
            0,
            quota,
        )

    def _response_error(self, response: ReadOnlyHttpResponse) -> ProviderErrorCode | None:
        return {
            400: ProviderErrorCode.INVALID_REQUEST,
            401: ProviderErrorCode.AUTHENTICATION_FAILED,
            403: ProviderErrorCode.ENTITLEMENT_MISSING,
            429: ProviderErrorCode.RATE_LIMITED,
        }.get(
            response.status_code,
            ProviderErrorCode.PROVIDER_UNAVAILABLE if response.status_code >= 500 else None,
        )

    def _failure(
        self,
        request: CapabilityRequest,
        code: ProviderErrorCode,
        response: ReadOnlyHttpResponse | None,
        attempts: tuple[ProviderAttemptMetadata, ...] | None,
    ) -> ProviderFetchResult:
        reference = response.request_reference if response is not None else None
        error = normalized_provider_error(
            code, f"Tradier {code.value}", "tradier", request.capability, reference
        )
        if attempts is None:
            metadata = ProviderResponseMetadata(
                "tradier",
                reference or "no-request",
                self._dependencies.clock.now(),
                "not_sent",
                0,
                0,
            )
            attempts = (ProviderAttemptMetadata("tradier", request.capability, 1, 1, metadata),)
        return ProviderFetchResult((), error, attempts)


def _mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    nested = value[key]
    if not isinstance(nested, Mapping):
        raise TypeError("expected object")
    return cast(Mapping[str, object], nested)


def _rows(value: object) -> tuple[Mapping[str, object], ...]:
    values: Sequence[object] = value if isinstance(value, list) else [value]
    if not values or values == [None] or not all(isinstance(item, Mapping) for item in values):
        raise _EmptyPayload("expected non-empty rows")
    return tuple(cast(Mapping[str, object], item) for item in values)


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _date(value: object) -> date:
    return date.fromisoformat(str(value))


def _is_monthly_expiration(value: date) -> bool:
    return value.weekday() == 4 and 15 <= value.day <= 21


def _observed_at(row: Mapping[str, object], fallback: datetime) -> datetime:
    raw = row.get("trade_date") or row.get("timestamp")
    if isinstance(raw, (int, float)):
        divisor = 1000 if raw > 10_000_000_000 else 1
        return datetime.fromtimestamp(raw / divisor, tz=timezone.utc)
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    return fallback


def _evidence(response: ReadOnlyHttpResponse) -> tuple[EvidenceReference, ...]:
    return (EvidenceReference(EvidenceKind.OBSERVATION, f"tradier:{response.request_reference}"),)


def _quote(subject: MarketDataSubject, row: Mapping[str, object]) -> Quote:
    return Quote(
        subject.canonical_instrument,
        _decimal(row["bid"]),
        _decimal(row["ask"]),
        _decimal(row["last"]),
        _decimal(row["bidsize"]) if row.get("bidsize") is not None else None,
        _decimal(row["asksize"]) if row.get("asksize") is not None else None,
        _decimal(row["volume"]) if row.get("volume") is not None else None,
        subject.canonical_instrument.currency,
    )


def _bar(subject: MarketDataSubject, row: Mapping[str, object]) -> OHLCVBar:
    day = _date(row["date"])
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return OHLCVBar(
        subject.canonical_instrument,
        86400,
        start,
        start + timedelta(days=1),
        _decimal(row["open"]),
        _decimal(row["high"]),
        _decimal(row["low"]),
        _decimal(row["close"]),
        _decimal(row["volume"]),
    )


def _security(subject: MarketDataSubject, symbol: str) -> Security:
    return Security(subject.canonical_instrument, symbol.upper(), SecurityAssetType.EQUITY, "US")


def _chain(
    subject: MarketDataSubject,
    rows: tuple[Mapping[str, object], ...],
    response: ReadOnlyHttpResponse,
    received_at: datetime,
) -> OptionChain:
    if not rows:
        raise ValueError("empty option chain")
    observed = _observed_at(rows[0], received_at)
    evidence = _evidence(response)
    symbol = str(rows[0].get("underlying") or subject.canonical_instrument.display_symbol)
    security = _security(subject, symbol)
    contracts = tuple(_option(security, row, observed, evidence) for row in rows)
    return OptionChain(
        f"tradier:{response.request_reference}", security, observed, contracts, evidence
    )


def _option(
    security: Security,
    row: Mapping[str, object],
    observed: datetime,
    evidence: tuple[EvidenceReference, ...],
) -> OptionContract:
    greeks = row.get("greeks") if isinstance(row.get("greeks"), Mapping) else {}
    values = cast(Mapping[str, object], greeks)
    option_type = OptionType.CALL if str(row["option_type"]).lower() == "call" else OptionType.PUT

    def optional(name: str) -> Decimal | None:
        raw = values.get(name, row.get(name))
        return None if raw is None else _decimal(raw)

    return OptionContract(
        CanonicalInstrumentIdentity("occ", str(row["symbol"])),
        security,
        _date(row["expiration_date"]),
        _decimal(row["strike"]),
        option_type,
        optional("bid"),
        optional("ask"),
        optional("last"),
        int(str(row["volume"])) if row.get("volume") is not None else None,
        int(str(row["open_interest"])) if row.get("open_interest") is not None else None,
        optional("delta"),
        optional("gamma"),
        optional("theta"),
        optional("vega"),
        optional("rho"),
        optional("mid_iv"),
        observed,
        evidence,
    )


def _field_present(field: str, value: object) -> bool:
    if field == "expirations":
        return isinstance(value, ExpirationCycle)
    if field == "contracts":
        return isinstance(value, OptionChain) and bool(value.contracts)
    if field in {"greeks", "implied_volatility", "volume", "open_interest"} and isinstance(
        value, OptionChain
    ):
        attribute = {
            "greeks": "delta",
            "implied_volatility": "implied_volatility",
            "volume": "volume",
            "open_interest": "open_interest",
        }[field]
        return all(getattr(contract, attribute) is not None for contract in value.contracts)
    return hasattr(value, field) and getattr(value, field) is not None


def tradier_provider_registration() -> ProviderRegistration:
    return ProviderRegistration("tradier", "v1", TradierProvider)
