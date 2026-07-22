"""Read-only Finnhub Market Data adapter and candle diagnostics (MD-010)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import cast

from domain import (
    AnnouncementTime,
    CompletenessMetadata,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataSubject,
    MarketObservation,
    OHLCVBar,
    ProviderProvenance,
    Quote,
    Security,
    SecurityAssetType,
    market_observation_identity,
)
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

FINNHUB_CAPABILITIES = (
    MarketCapability.REAL_TIME_QUOTE_V1,
    MarketCapability.HISTORICAL_BARS_V1,
    MarketCapability.EARNINGS_CALENDAR_V1,
)


class _NoData(ValueError):
    pass


class _EmptyPayload(ValueError):
    pass


class FinnhubProvider:
    def __init__(self, config: ProviderConfig, dependencies: ProviderDependencies) -> None:
        if config.provider_id != "finnhub" or config.credential is None:
            raise ValueError("Finnhub requires explicit enabled credential configuration")
        if not isinstance(dependencies.transport, ReadOnlyHttpTransport):
            raise ValueError("Finnhub requires an injected read-only HTTP transport")
        self._config = config
        self._credential = config.credential
        self._dependencies = dependencies
        self._transport = dependencies.transport
        self._metadata = ProviderMetadata(
            ProviderIdentity("finnhub", "finnhub", config.adapter_version),
            FINNHUB_CAPABILITIES,
            (ProviderLimitDeclaration("global_calls_per_second", "30", "documented"),),
            FINNHUB_CAPABILITIES,
            "v1",
        )

    @property
    def provider_id(self) -> str:
        return "finnhub"

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
            raise DomainInvariantError("Finnhub request budget provider mismatch")
        if request.capability not in self.capabilities:
            return self._failure(request, ProviderErrorCode.UNSUPPORTED_CAPABILITY, None, ())
        observations: list[MarketObservation] = []
        attempts: list[ProviderAttemptMetadata] = []
        for subject in request.subjects:
            symbol = subject.projection_for(
                "finnhub", "symbol", request.effective_end
            ).address_value
            path, query, endpoint_class = self._endpoint(request, symbol)
            try:
                response = self._transport.get(
                    ReadOnlyHttpRequest(
                        self._config.endpoint_environment.value,
                        endpoint_class,
                        path,
                        query,
                        (
                            ("Accept", "application/json"),
                            ("X-Finnhub-Token", self._credential.reveal()),
                        ),
                        self._config.timeout_seconds,
                    )
                )
            except ReadOnlyTransportTimeout:
                return self._failure(request, ProviderErrorCode.TIMEOUT, None, tuple(attempts))
            except ReadOnlyTransportError:
                return self._failure(
                    request, ProviderErrorCode.TRANSPORT_ERROR, None, tuple(attempts)
                )
            attempts.append(
                ProviderAttemptMetadata(
                    "finnhub",
                    request.capability,
                    len(attempts) + 1,
                    1,
                    self._response_metadata(response),
                )
            )
            error = self._http_error(response)
            if error is not None:
                return self._failure(request, error, response, tuple(attempts))
            semantic_error = self._provider_error(response)
            if semantic_error is not None:
                return self._failure(request, semantic_error, response, tuple(attempts))
            try:
                observations.extend(self._normalize(request, subject, response))
            except _NoData:
                return self._failure(request, ProviderErrorCode.NO_DATA, response, tuple(attempts))
            except _EmptyPayload:
                return self._failure(
                    request, ProviderErrorCode.EMPTY_PAYLOAD, response, tuple(attempts)
                )
            except (KeyError, TypeError, ValueError, InvalidOperation, DomainInvariantError):
                return self._failure(
                    request, ProviderErrorCode.SCHEMA_MISMATCH, response, tuple(attempts)
                )
        return (
            ProviderFetchResult(tuple(observations), None, tuple(attempts))
            if observations
            else self._failure(request, ProviderErrorCode.EMPTY_PAYLOAD, None, tuple(attempts))
        )

    def health(self, probe: HealthProbe) -> ProviderHealthReport:
        return ProviderHealthReport(
            "finnhub", ProviderStatus.UNKNOWN, probe.requested_at, "NOT_PROBED", None
        )

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport:
        started = self._dependencies.clock.now()
        subjects = {item.requested_capability: item for item in plan.subjects}
        checks: list[ValidationCheckResult] = []
        attempts: list[ProviderAttemptMetadata] = []
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
            context = subject.request_context
            authorization = self._dependencies.budget_authorizer.authorize("finnhub", capability, 1)
            result = self.fetch(
                CapabilityRequest(
                    capability,
                    (subject,),
                    context.semantic_start,
                    context.semantic_end,
                    context.required_fields,
                    86400,
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
                    "bounded Finnhub semantic check completed",
                )
            )
        completed = self._dependencies.clock.now()
        report_id = hashlib.sha256(
            f"{plan.plan_id}:{started.isoformat()}:{completed.isoformat()}".encode()
        ).hexdigest()
        return ProviderValidationReport(
            report_id,
            plan.plan_id,
            "finnhub",
            self._config.adapter_version,
            started,
            completed,
            tuple(checks),
            tuple(attempts),
        )

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport("finnhub", self._dependencies.clock.now())

    def _endpoint(
        self, request: CapabilityRequest, symbol: str
    ) -> tuple[str, tuple[tuple[str, str], ...], str]:
        if request.capability is MarketCapability.REAL_TIME_QUOTE_V1:
            return "/api/v1/quote", (("symbol", symbol),), "quote"
        if request.capability is MarketCapability.HISTORICAL_BARS_V1:
            return (
                "/api/v1/stock/candle",
                (
                    ("from", str(int(request.effective_start.timestamp()))),
                    ("resolution", "D"),
                    ("symbol", symbol),
                    ("to", str(int(request.effective_end.timestamp()))),
                ),
                "stock_candle",
            )
        return (
            "/api/v1/calendar/earnings",
            (
                ("from", request.effective_start.date().isoformat()),
                ("symbol", symbol),
                ("to", request.effective_end.date().isoformat()),
            ),
            "earnings_calendar",
        )

    def _normalize(
        self, request: CapabilityRequest, subject: MarketDataSubject, response: ReadOnlyHttpResponse
    ) -> tuple[MarketObservation, ...]:
        if request.capability is MarketCapability.REAL_TIME_QUOTE_V1:
            if not response.json_body or response.json_body.get("c") in (None, 0, 0.0):
                raise _EmptyPayload
            value = Quote(
                subject.canonical_instrument,
                None,
                None,
                _decimal(response.json_body["c"]),
                None,
                None,
                None,
                subject.canonical_instrument.currency,
            )
            effective = _timestamp(response.json_body.get("t"))
            return (self._observation(request, subject, value, effective, response),)
        if request.capability is MarketCapability.HISTORICAL_BARS_V1:
            status = response.json_body.get("s")
            if status == "no_data":
                raise _NoData
            if status != "ok":
                raise ValueError("invalid candle status")
            arrays = tuple(
                _array(response.json_body, key) for key in ("o", "h", "l", "c", "v", "t")
            )
            if not arrays[0]:
                raise _EmptyPayload
            if len({len(value) for value in arrays}) != 1:
                raise ValueError("inconsistent candle arrays")
            bar_values = tuple(
                OHLCVBar(
                    subject.canonical_instrument,
                    86400,
                    _timestamp(arrays[5][index]),
                    _timestamp(arrays[5][index]) + timedelta(days=1),
                    _decimal(arrays[0][index]),
                    _decimal(arrays[1][index]),
                    _decimal(arrays[2][index]),
                    _decimal(arrays[3][index]),
                    _decimal(arrays[4][index]),
                )
                for index in range(len(arrays[0]))
            )
            return tuple(
                self._observation(request, subject, value, value.end_at, response)
                for value in bar_values
            )
        rows = _rows(response.json_body.get("earningsCalendar"))
        security = Security(
            subject.canonical_instrument,
            subject.canonical_instrument.display_symbol.upper(),
            SecurityAssetType.EQUITY,
            "US",
        )
        earnings_values = tuple(
            EarningsEvent(
                f"finnhub:{row['symbol']}:{row['date']}",
                security,
                datetime.fromisoformat(str(row["date"])).date(),
                {
                    "bmo": AnnouncementTime.BEFORE_OPEN,
                    "amc": AnnouncementTime.AFTER_CLOSE,
                    "dmh": AnnouncementTime.DURING_MARKET,
                }.get(str(row.get("hour")), AnnouncementTime.UNKNOWN),
                None,
                True,
                (),
                self._dependencies.clock.now(),
                _evidence(response),
            )
            for row in rows
        )
        return tuple(
            self._observation(request, subject, value, value.observed_at, response)
            for value in earnings_values
        )

    def _observation(
        self,
        request: CapabilityRequest,
        subject: MarketDataSubject,
        value: MarketObservationValue,
        effective: datetime,
        response: ReadOnlyHttpResponse,
    ) -> MarketObservation:
        received = self._dependencies.clock.now().astimezone(timezone.utc)
        age = max(0, int((received - effective).total_seconds()))
        present = tuple(field for field in request.required_fields if _present(field, value))
        missing = tuple(field for field in request.required_fields if field not in present)
        provenance = ProviderProvenance("finnhub", response.request_reference, _evidence(response))
        identity = market_observation_identity(
            "finnhub", request.capability, subject, effective, value, "v1"
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
            FreshnessMetadata(
                received,
                effective,
                request.maximum_age_seconds,
                age,
                FreshnessStatus.FRESH
                if age <= request.maximum_age_seconds
                else FreshnessStatus.STALE,
            ),
            CompletenessMetadata(request.required_fields, present, missing),
        )

    def _response_metadata(self, response: ReadOnlyHttpResponse) -> ProviderResponseMetadata:
        quota = tuple(
            (key.lower(), value) for key, value in response.headers if "ratelimit" in key.lower()
        )
        return ProviderResponseMetadata(
            "finnhub",
            response.request_reference,
            self._dependencies.clock.now(),
            str(response.status_code),
            response.latency_milliseconds,
            0,
            quota,
        )

    def _http_error(self, response: ReadOnlyHttpResponse) -> ProviderErrorCode | None:
        if response.status_code == 403:
            detail = str(response.json_body.get("error", "")).lower()
            return (
                ProviderErrorCode.ENTITLEMENT_MISSING
                if any(token in detail for token in ("premium", "entitlement", "subscription"))
                else ProviderErrorCode.AUTHORIZATION_FAILED
            )
        return {
            401: ProviderErrorCode.AUTHENTICATION_FAILED,
            429: ProviderErrorCode.RATE_LIMITED,
        }.get(
            response.status_code,
            ProviderErrorCode.PROVIDER_UNAVAILABLE
            if response.status_code >= 500
            else ProviderErrorCode.INVALID_REQUEST
            if response.status_code >= 400
            else None,
        )

    def _provider_error(self, response: ReadOnlyHttpResponse) -> ProviderErrorCode | None:
        detail = response.json_body.get("error")
        if not isinstance(detail, str):
            return None
        normalized = detail.lower()
        if any(token in normalized for token in ("premium", "entitlement", "subscription")):
            return ProviderErrorCode.ENTITLEMENT_MISSING
        return ProviderErrorCode.INVALID_REQUEST

    def _failure(
        self,
        request: CapabilityRequest,
        code: ProviderErrorCode,
        response: ReadOnlyHttpResponse | None,
        attempts: tuple[ProviderAttemptMetadata, ...],
    ) -> ProviderFetchResult:
        if not attempts:
            metadata = ProviderResponseMetadata(
                "finnhub", "no-request", self._dependencies.clock.now(), "not_sent", 0, 0
            )
            attempts = (ProviderAttemptMetadata("finnhub", request.capability, 1, 1, metadata),)
        return ProviderFetchResult(
            (),
            normalized_provider_error(
                code,
                f"Finnhub {code.value}",
                "finnhub",
                request.capability,
                response.request_reference if response else None,
            ),
            attempts,
        )


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _timestamp(value: object) -> datetime:
    if not isinstance(value, (int, float)):
        raise TypeError("timestamp must be numeric")
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _array(body: Mapping[str, object], key: str) -> Sequence[object]:
    value = body.get(key)
    if not isinstance(value, list):
        raise TypeError("candle field must be an array")
    return value


def _rows(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise _EmptyPayload
    if not all(isinstance(item, Mapping) for item in value):
        raise TypeError("earnings rows must be objects")
    return tuple(cast(Mapping[str, object], item) for item in value)


def _evidence(response: ReadOnlyHttpResponse) -> tuple[EvidenceReference, ...]:
    return (EvidenceReference(EvidenceKind.OBSERVATION, f"finnhub:{response.request_reference}"),)


def _present(field: str, value: object) -> bool:
    aliases = {"earnings_date": "earnings_date", "last": "last"}
    return (
        hasattr(value, aliases.get(field, field))
        and getattr(value, aliases.get(field, field)) is not None
    )


def finnhub_provider_registration() -> ProviderRegistration:
    return ProviderRegistration("finnhub", "v1", FinnhubProvider)
