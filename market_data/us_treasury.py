"""Read-only US Treasury daily bill-rate adapter (X04, SP-01B).

Source: U.S. Department of the Treasury, "Daily Treasury Bill Rates"
(public, no credential, no fee). This is the published bank-discount
rate Cboe's PutWrite methodology names. Only the series this feed
publishes are served. Every other rate series is unsupported here and stays
a typed UNKNOWN for its consumer.

Point-in-time rule: a value for date D is effective at the 16:00 ET close of
D. It is returned only if that instant is no later than the request's
effective end, so an evaluation never sees a rate published after it.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ElementTree  # noqa: S405 -- DTD/entities rejected before parsing
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from zoneinfo import ZoneInfo

from domain import (
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    MarketCapability,
    MarketDataSubject,
    MarketObservation,
    ProviderProvenance,
    RateObservation,
    market_observation_identity,
)
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
from market_data.rate_series import RATE_SERIES, RATE_SERIES_SCHEME
from market_data.session_calendar import classify_market_data_freshness
from market_data.transport import (
    ReadOnlyHttpRequest,
    ReadOnlyHttpResponse,
    ReadOnlyHttpTransport,
    ReadOnlyTransportError,
    ReadOnlyTransportTimeout,
)

PROVIDER_ID = "us_treasury"
US_TREASURY_CAPABILITIES = (MarketCapability.RATE_OBSERVATION_V1,)
FEED_PATH = "/resource-center/data-chart-center/interest-rates/pages/xml"
MAX_FEED_CHARACTERS = 2_000_000
_NEW_YORK = ZoneInfo("America/New_York")
_ATOM = "{http://www.w3.org/2005/Atom}"
_METADATA = "{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
_DATA = "{http://schemas.microsoft.com/ado/2007/08/dataservices}"

# Canonical series -> the feed's published field (percent units).
FEED_FIELD_BY_SERIES = MappingProxyType(
    {
        "US_TBILL_4WK_BANK_DISCOUNT": "ROUND_B1_CLOSE_4WK_2",
        "US_TBILL_8WK_BANK_DISCOUNT": "ROUND_B1_CLOSE_8WK_2",
        "US_TBILL_13WK_BANK_DISCOUNT": "ROUND_B1_CLOSE_13WK_2",
        "US_TBILL_26WK_BANK_DISCOUNT": "ROUND_B1_CLOSE_26WK_2",
        "US_TBILL_4WK_COUPON_EQUIVALENT": "ROUND_B1_YIELD_4WK_2",
        "US_TBILL_8WK_COUPON_EQUIVALENT": "ROUND_B1_YIELD_8WK_2",
        "US_TBILL_13WK_COUPON_EQUIVALENT": "ROUND_B1_YIELD_13WK_2",
        "US_TBILL_26WK_COUPON_EQUIVALENT": "ROUND_B1_YIELD_26WK_2",
    }
)


class _FeedError(ValueError):
    pass


def publication_effective_time(day: date) -> datetime:
    """The 16:00 ET close of the publication date, in UTC."""
    return datetime.combine(day, time(16), _NEW_YORK).astimezone(UTC)


def parse_bill_rate_feed(text: str) -> dict[date, dict[str, Decimal]]:
    """Parse the Atom/OData feed into {date: {field: percent}}; empty values are absent."""
    if len(text) > MAX_FEED_CHARACTERS:
        raise _FeedError("feed exceeds size bound")
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise _FeedError("feed declares a DTD or entity")
    root = ElementTree.fromstring(text)  # noqa: S314 -- bounded, DTD/entity-free input
    rows: dict[date, dict[str, Decimal]] = {}
    for entry in root.iter(f"{_ATOM}entry"):
        properties = next(entry.iter(f"{_METADATA}properties"), None)
        if properties is None:
            continue
        index_date = properties.find(f"{_DATA}INDEX_DATE")
        if index_date is None or not (index_date.text or "").strip():
            continue
        day = datetime.fromisoformat(str(index_date.text).strip()).date()
        values: dict[str, Decimal] = {}
        for element in properties:
            name = element.tag.removeprefix(_DATA)
            raw = (element.text or "").strip()
            if name in FEED_FIELD_BY_SERIES.values() and raw:
                values[name] = Decimal(raw)
        rows[day] = values
    return rows


def _previous_month(day: date) -> date:
    return date(day.year - 1, 12, 1) if day.month == 1 else date(day.year, day.month - 1, 1)


class UsTreasuryProvider:
    """Official public Treasury feed; read-only GET, no credential, no account surface."""

    def __init__(self, config: ProviderConfig, dependencies: ProviderDependencies) -> None:
        if config.provider_id != PROVIDER_ID:
            raise ValueError("UsTreasuryProvider requires the us_treasury configuration")
        if not isinstance(dependencies.transport, ReadOnlyHttpTransport):
            raise ValueError("UsTreasuryProvider requires an injected read-only HTTP transport")
        self._config = config
        self._dependencies = dependencies
        self._transport = dependencies.transport
        self._metadata = ProviderMetadata(
            ProviderIdentity(PROVIDER_ID, PROVIDER_ID, config.adapter_version),
            US_TREASURY_CAPABILITIES,
            (),
            US_TREASURY_CAPABILITIES,
            "v1",
        )

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    @property
    def capabilities(self) -> tuple[MarketCapability, ...]:
        return self.metadata.capabilities

    def fetch(
        self, request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        if budget.provider_id != PROVIDER_ID:
            raise DomainInvariantError("US Treasury request budget provider mismatch")
        if request.capability not in self.capabilities:
            return self._failure(request, ProviderErrorCode.UNSUPPORTED_CAPABILITY, None, ())
        observations: list[MarketObservation] = []
        attempts: list[ProviderAttemptMetadata] = []
        for subject in request.subjects:
            identity = subject.canonical_instrument.identity
            field = FEED_FIELD_BY_SERIES.get(identity.value)
            if identity.scheme != RATE_SERIES_SCHEME or field is None:
                return self._failure(
                    request, ProviderErrorCode.UNSUPPORTED_SYMBOL, None, tuple(attempts)
                )
            end_day = request.effective_end.astimezone(_NEW_YORK).date()
            start_day = request.effective_start.astimezone(_NEW_YORK).date()
            months = [date(end_day.year, end_day.month, 1)]
            if start_day < months[0]:
                months.append(_previous_month(months[0]))
            selected: tuple[date, Decimal, ReadOnlyHttpResponse] | None = None
            for month in months:
                try:
                    response = self._transport.get(self._request(month))
                except ReadOnlyTransportTimeout:
                    return self._failure(request, ProviderErrorCode.TIMEOUT, None, tuple(attempts))
                except ReadOnlyTransportError:
                    return self._failure(
                        request, ProviderErrorCode.TRANSPORT_ERROR, None, tuple(attempts)
                    )
                attempts.append(
                    ProviderAttemptMetadata(
                        PROVIDER_ID,
                        request.capability,
                        len(attempts) + 1,
                        1,
                        self._response_metadata(response),
                    )
                )
                if response.status_code >= 400:
                    code = (
                        ProviderErrorCode.PROVIDER_UNAVAILABLE
                        if response.status_code >= 500
                        else ProviderErrorCode.INVALID_REQUEST
                    )
                    return self._failure(request, code, response, tuple(attempts))
                text = response.json_body.get("text")
                if not isinstance(text, str):
                    return self._failure(
                        request, ProviderErrorCode.SCHEMA_MISMATCH, response, tuple(attempts)
                    )
                try:
                    rows = parse_bill_rate_feed(text)
                except (_FeedError, ElementTree.ParseError, ValueError, InvalidOperation):
                    return self._failure(
                        request, ProviderErrorCode.SCHEMA_MISMATCH, response, tuple(attempts)
                    )
                eligible = sorted(
                    (day, values[field])
                    for day, values in rows.items()
                    if field in values
                    and start_day <= day
                    and publication_effective_time(day) <= request.effective_end
                )
                if eligible:
                    selected = (eligible[-1][0], eligible[-1][1], response)
                    break
            if selected is None:
                return self._failure(request, ProviderErrorCode.NO_DATA, None, tuple(attempts))
            day, percent, response = selected
            definition = RATE_SERIES[identity.value]
            value = RateObservation(
                subject.canonical_instrument,
                definition.basis,
                definition.tenor_days,
                percent / Decimal(100),
                day,
            )
            observations.append(
                self._observation(
                    request, subject, value, publication_effective_time(day), response
                )
            )
        return ProviderFetchResult(tuple(observations), None, tuple(attempts))

    def health(self, probe: HealthProbe) -> ProviderHealthReport:
        return ProviderHealthReport(
            PROVIDER_ID, ProviderStatus.UNKNOWN, probe.requested_at, "NOT_PROBED", None
        )

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport:
        now = self._dependencies.clock.now()
        report_id = hashlib.sha256(f"{plan.plan_id}:{now.isoformat()}".encode()).hexdigest()
        checks = tuple(
            ValidationCheckResult(
                capability.value,
                ValidationCheckStatus.SKIPPED,
                "INCONCLUSIVE",
                "public feed; validated through bounded fetch tests",
            )
            for capability in (plan.capabilities or US_TREASURY_CAPABILITIES)
        )
        return ProviderValidationReport(
            report_id, plan.plan_id, PROVIDER_ID, self._config.adapter_version, now, now, checks, ()
        )

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport(PROVIDER_ID, self._dependencies.clock.now())

    def _request(self, month: date) -> ReadOnlyHttpRequest:
        return ReadOnlyHttpRequest(
            self._config.endpoint_environment.value,
            "daily_treasury_bill_rates",
            FEED_PATH,
            (
                ("data", "daily_treasury_bill_rates"),
                ("field_tdr_date_value_month", f"{month.year:04d}{month.month:02d}"),
            ),
            (("Accept", "application/xml"),),
            self._config.timeout_seconds,
        )

    def _observation(
        self,
        request: CapabilityRequest,
        subject: MarketDataSubject,
        value: RateObservation,
        effective: datetime,
        response: ReadOnlyHttpResponse,
    ) -> MarketObservation:
        received = self._dependencies.clock.now().astimezone(UTC)
        evidence = (
            EvidenceReference(
                EvidenceKind.OBSERVATION, f"{PROVIDER_ID}:{response.request_reference}"
            ),
        )
        return MarketObservation(
            market_observation_identity(
                PROVIDER_ID, request.capability, subject, effective, value, "v1"
            ),
            request.capability,
            subject,
            effective,
            received,
            value,
            "v1",
            ProviderProvenance(PROVIDER_ID, response.request_reference, evidence),
            classify_market_data_freshness(received, effective, request.maximum_age_seconds),
            CompletenessMetadata(
                request.required_fields,
                tuple(field for field in request.required_fields if field == "value"),
                tuple(field for field in request.required_fields if field != "value"),
            ),
        )

    def _response_metadata(self, response: ReadOnlyHttpResponse) -> ProviderResponseMetadata:
        return ProviderResponseMetadata(
            PROVIDER_ID,
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
                PROVIDER_ID, "no-request", self._dependencies.clock.now(), "not_sent", 0, 0
            )
            attempts = (ProviderAttemptMetadata(PROVIDER_ID, request.capability, 1, 1, metadata),)
        return ProviderFetchResult(
            (),
            normalized_provider_error(
                code,
                f"US Treasury {code.value}",
                PROVIDER_ID,
                request.capability,
                response.request_reference if response else None,
            ),
            attempts,
        )


def us_treasury_provider_registration() -> ProviderRegistration:
    return ProviderRegistration(PROVIDER_ID, "v1", UsTreasuryProvider)
