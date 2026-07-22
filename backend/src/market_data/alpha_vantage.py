"""Read-only Alpha Vantage fallback Market Data adapter (MD-011)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, time, timedelta, timezone
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

ALPHA_VANTAGE_CAPABILITIES = (
    MarketCapability.HISTORICAL_BARS_V1,
    MarketCapability.EARNINGS_CALENDAR_V1,
)


class _NoData(ValueError):
    pass


class _EmptyPayload(ValueError):
    pass


class AlphaVantageProvider:
    def __init__(self, config: ProviderConfig, dependencies: ProviderDependencies) -> None:
        if config.provider_id != "alpha_vantage" or config.credential is None:
            raise ValueError("Alpha Vantage requires explicit enabled credential configuration")
        if not isinstance(dependencies.transport, ReadOnlyHttpTransport):
            raise ValueError("Alpha Vantage requires an injected read-only HTTP transport")
        self._config = config
        self._credential = config.credential
        self._dependencies = dependencies
        self._transport = dependencies.transport
        self._metadata = ProviderMetadata(
            ProviderIdentity("alpha_vantage", "alpha_vantage", config.adapter_version),
            ALPHA_VANTAGE_CAPABILITIES,
            (
                ProviderLimitDeclaration("daily_output_default", "compact", "documented"),
                ProviderLimitDeclaration("daily_adjustment", "raw_as_traded", "documented"),
            ),
            ALPHA_VANTAGE_CAPABILITIES,
            "v1",
        )

    @property
    def provider_id(self) -> str:
        return "alpha_vantage"

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
            raise DomainInvariantError("Alpha Vantage request budget provider mismatch")
        if request.capability not in self.capabilities:
            return self._failure(request, ProviderErrorCode.UNSUPPORTED_CAPABILITY, None, ())
        observations: list[MarketObservation] = []
        attempts: list[ProviderAttemptMetadata] = []
        for subject in request.subjects:
            symbol = subject.projection_for(
                "alpha_vantage", "symbol", request.effective_end
            ).address_value
            query = (
                ("apikey", self._credential.reveal()),
                (
                    "function",
                    "TIME_SERIES_DAILY"
                    if request.capability is MarketCapability.HISTORICAL_BARS_V1
                    else "EARNINGS",
                ),
                ("outputsize", "compact"),
                ("symbol", symbol),
            )
            try:
                response = self._transport.get(
                    ReadOnlyHttpRequest(
                        self._config.endpoint_environment.value,
                        "daily_bars"
                        if request.capability is MarketCapability.HISTORICAL_BARS_V1
                        else "earnings",
                        "/query",
                        query,
                        (("Accept", "application/json"),),
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
                    self.provider_id,
                    request.capability,
                    len(attempts) + 1,
                    1,
                    self._response_metadata(response),
                )
            )
            error = self._error(response)
            if error is not None:
                return self._failure(request, error, response, tuple(attempts))
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
            self.provider_id, ProviderStatus.UNKNOWN, probe.requested_at, "NOT_PROBED", None
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
            authorization = self._dependencies.budget_authorizer.authorize(
                self.provider_id, capability, 1
            )
            result = self.fetch(
                CapabilityRequest(
                    capability,
                    (subject,),
                    context.semantic_start,
                    context.semantic_end,
                    context.required_fields,
                    86400 * 120,
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
                    "bounded Alpha Vantage semantic check completed",
                )
            )
        completed = self._dependencies.clock.now()
        identity = hashlib.sha256(
            f"{plan.plan_id}:{started.isoformat()}:{completed.isoformat()}".encode()
        ).hexdigest()
        return ProviderValidationReport(
            identity,
            plan.plan_id,
            self.provider_id,
            self._config.adapter_version,
            started,
            completed,
            tuple(checks),
            tuple(attempts),
        )

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport(self.provider_id, self._dependencies.clock.now())

    def _normalize(
        self, request: CapabilityRequest, subject: MarketDataSubject, response: ReadOnlyHttpResponse
    ) -> tuple[MarketObservation, ...]:
        if request.capability is MarketCapability.HISTORICAL_BARS_V1:
            series = response.json_body.get("Time Series (Daily)")
            if not isinstance(series, Mapping):
                raise _EmptyPayload
            values: list[MarketObservation] = []
            for raw_date, raw_row in sorted(series.items()):
                day = datetime.fromisoformat(str(raw_date)).date()
                if not request.effective_start.date() <= day <= request.effective_end.date():
                    continue
                if not isinstance(raw_row, Mapping):
                    raise TypeError("daily row must be an object")
                row = cast(Mapping[str, object], raw_row)
                start = datetime.combine(day, time.min, tzinfo=timezone.utc)
                bar = OHLCVBar(
                    subject.canonical_instrument,
                    86400,
                    start,
                    start + timedelta(days=1),
                    _decimal(row["1. open"]),
                    _decimal(row["2. high"]),
                    _decimal(row["3. low"]),
                    _decimal(row["4. close"]),
                    _decimal(row["5. volume"]),
                )
                values.append(self._observation(request, subject, bar, bar.end_at, response))
            if not values:
                raise _NoData
            return tuple(values)
        rows = response.json_body.get("quarterlyEarnings")
        if not isinstance(rows, list) or not rows:
            raise _EmptyPayload
        security = Security(
            subject.canonical_instrument,
            subject.canonical_instrument.display_symbol.upper(),
            SecurityAssetType.EQUITY,
            "US",
        )
        observations: list[MarketObservation] = []
        for raw_row in rows:
            if not isinstance(raw_row, Mapping):
                raise TypeError("earnings row must be an object")
            row = cast(Mapping[str, object], raw_row)
            event_date = datetime.fromisoformat(
                str(row.get("reportedDate") or row["fiscalDateEnding"])
            ).date()
            if not request.effective_start.date() <= event_date <= request.effective_end.date():
                continue
            event = EarningsEvent(
                f"alpha_vantage:{row.get('symbol', security.symbol)}:{event_date.isoformat()}",
                security,
                event_date,
                AnnouncementTime.UNKNOWN,
                None,
                row.get("reportedEPS") not in (None, "None"),
                (),
                self._dependencies.clock.now(),
                _evidence(response),
            )
            observations.append(
                self._observation(request, subject, event, event.observed_at, response)
            )
        if not observations:
            raise _NoData
        return tuple(observations)

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
        present = tuple(
            field
            for field in request.required_fields
            if hasattr(value, field) and getattr(value, field) is not None
        )
        missing = tuple(field for field in request.required_fields if field not in present)
        provenance = ProviderProvenance(
            self.provider_id, response.request_reference, _evidence(response)
        )
        identity = market_observation_identity(
            self.provider_id, request.capability, subject, effective, value, "v1"
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

    def _error(self, response: ReadOnlyHttpResponse) -> ProviderErrorCode | None:
        if response.status_code == 401:
            return ProviderErrorCode.AUTHENTICATION_FAILED
        if response.status_code == 403:
            return ProviderErrorCode.AUTHORIZATION_FAILED
        if response.status_code == 429:
            return ProviderErrorCode.RATE_LIMITED
        if response.status_code >= 500:
            return ProviderErrorCode.PROVIDER_UNAVAILABLE
        if response.status_code >= 400:
            return ProviderErrorCode.INVALID_REQUEST
        if "Note" in response.json_body:
            return ProviderErrorCode.RATE_LIMITED
        information = response.json_body.get("Information")
        if isinstance(information, str):
            lowered = information.lower()
            if any(value in lowered for value in ("rate", "frequency", "limit")):
                return ProviderErrorCode.RATE_LIMITED
            if any(value in lowered for value in ("premium", "subscription")):
                return ProviderErrorCode.ENTITLEMENT_MISSING
            return ProviderErrorCode.INVALID_REQUEST
        error = response.json_body.get("Error Message")
        if isinstance(error, str):
            return (
                ProviderErrorCode.AUTHENTICATION_FAILED
                if "api key" in error.lower()
                else ProviderErrorCode.INVALID_REQUEST
            )
        return None

    def _response_metadata(self, response: ReadOnlyHttpResponse) -> ProviderResponseMetadata:
        return ProviderResponseMetadata(
            self.provider_id,
            response.request_reference,
            self._dependencies.clock.now(),
            str(response.status_code),
            response.latency_milliseconds,
            0,
        )

    def _failure(
        self,
        request: CapabilityRequest,
        code: ProviderErrorCode,
        response: ReadOnlyHttpResponse | None,
        attempts: tuple[ProviderAttemptMetadata, ...],
    ) -> ProviderFetchResult:
        if not attempts:
            metadata = ProviderResponseMetadata(
                self.provider_id, "no-request", self._dependencies.clock.now(), "not_sent", 0, 0
            )
            attempts = (
                ProviderAttemptMetadata(self.provider_id, request.capability, 1, 1, metadata),
            )
        return ProviderFetchResult(
            (),
            normalized_provider_error(
                code,
                f"Alpha Vantage {code.value}",
                self.provider_id,
                request.capability,
                response.request_reference if response else None,
            ),
            attempts,
        )


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _evidence(response: ReadOnlyHttpResponse) -> tuple[EvidenceReference, ...]:
    return (
        EvidenceReference(EvidenceKind.OBSERVATION, f"alpha_vantage:{response.request_reference}"),
    )


def alpha_vantage_provider_registration() -> ProviderRegistration:
    return ProviderRegistration("alpha_vantage", "v1", AlphaVantageProvider)
