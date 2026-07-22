from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    OHLCVBar,
    ProviderAddressProjection,
    Quote,
)
from market_data import (
    CapabilityRequest,
    ProviderDependencies,
    ProviderFactory,
    ProviderRegistry,
    ProviderValidationPlan,
    RequestBudgetAuthorization,
    load_market_data_config,
)
from market_data.finnhub import FinnhubProvider, finnhub_provider_registration
from market_data.providers import ProviderErrorCode
from market_data.transport import (
    ReadOnlyHttpRequest,
    ReadOnlyHttpResponse,
    ReadOnlyTransportError,
    ReadOnlyTransportTimeout,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"), InstrumentKind.EQUITY, "AAPL", "USD"
)


@dataclass(frozen=True)
class Clock:
    def now(self) -> datetime:
        return NOW


class Budget:
    def __init__(self) -> None:
        self.calls: list[tuple[str, MarketCapability, int]] = []

    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        self.calls.append((provider_id, capability, request_units))
        return RequestBudgetAuthorization("validation-budget", provider_id, request_units, 1)


class Transport:
    def __init__(self, outcomes: tuple[ReadOnlyHttpResponse | Exception, ...]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[ReadOnlyHttpRequest] = []

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(body: dict[str, object], status: int = 200) -> ReadOnlyHttpResponse:
    return ReadOnlyHttpResponse(status, body, (), 9, "finnhub-request-1")


def subject(capability: MarketCapability, fields: tuple[str, ...]) -> MarketDataSubject:
    kind = (
        MarketDataSubjectType.EARNINGS_SECURITY
        if capability is MarketCapability.EARNINGS_CALENDAR_V1
        else MarketDataSubjectType.INSTRUMENT
    )
    projection = ProviderAddressProjection(
        "finnhub", "v1", "symbol", "AAPL", NOW - timedelta(days=30), None, EVIDENCE
    )
    return MarketDataSubject(
        INSTRUMENT,
        kind,
        capability,
        MarketDataRequestContext(NOW - timedelta(days=5), NOW, fields, (projection,), EVIDENCE),
    )


def request(capability: MarketCapability, fields: tuple[str, ...]) -> CapabilityRequest:
    item = subject(capability, fields)
    return CapabilityRequest(
        capability,
        (item,),
        item.request_context.semantic_start,
        item.request_context.semantic_end,
        fields,
        86400 * 10,
    )


def provider(transport: Transport, budget: Budget | None = None) -> tuple[FinnhubProvider, Budget]:
    config = load_market_data_config(
        {"ASA_FINNHUB_ENABLED": "true", "ASA_FINNHUB_API_KEY": "test-key"}
    )
    selected = next(item for item in config.providers if item.provider_id == "finnhub")
    authorizer = budget or Budget()
    return (
        FinnhubProvider(selected, ProviderDependencies(transport, Clock(), authorizer)),
        authorizer,
    )


def authorization(provider_id: str = "finnhub") -> RequestBudgetAuthorization:
    return RequestBudgetAuthorization("budget", provider_id, 1, 1)


def test_quote_success_requires_semantic_price_and_timestamp() -> None:
    transport = Transport((response({"c": 210.25, "t": int(NOW.timestamp())}),))
    adapter, _ = provider(transport)
    result = adapter.fetch(request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization())
    assert result.error is None and isinstance(result.observations[0].value, Quote)
    assert transport.requests[0].path == "/api/v1/quote"
    assert transport.requests[0].query == (("symbol", "AAPL"),)
    assert "test-key" not in repr(transport.requests[0])


def test_candle_success_validates_status_arrays_and_utc_timestamps() -> None:
    stamp = int((NOW - timedelta(days=2)).timestamp())
    body = {
        "s": "ok",
        "o": [205],
        "h": [212],
        "l": [204],
        "c": [210],
        "v": [50000000],
        "t": [stamp],
    }
    transport = Transport((response(body),))
    adapter, _ = provider(transport)
    result = adapter.fetch(
        request(MarketCapability.HISTORICAL_BARS_V1, ("open", "high", "low", "close", "volume")),
        authorization(),
    )
    assert result.error is None and isinstance(result.observations[0].value, OHLCVBar)
    assert result.observations[0].value.start_at.tzinfo is timezone.utc
    assert dict(transport.requests[0].query)["resolution"] == "D"


def test_earnings_success_normalizes_calendar_event() -> None:
    transport = Transport(
        (response({"earningsCalendar": [{"symbol": "AAPL", "date": "2026-08-01", "hour": "amc"}]}),)
    )
    adapter, _ = provider(transport)
    result = adapter.fetch(
        request(MarketCapability.EARNINGS_CALENDAR_V1, ("earnings_date",)), authorization()
    )
    assert result.error is None and isinstance(result.observations[0].value, EarningsEvent)


@pytest.mark.parametrize(
    ("body", "expected"),
    (
        ({"s": "no_data"}, ProviderErrorCode.NO_DATA),
        (
            {"s": "ok", "o": [], "h": [], "l": [], "c": [], "v": [], "t": []},
            ProviderErrorCode.EMPTY_PAYLOAD,
        ),
        (
            {"s": "ok", "o": [1], "h": [1, 2], "l": [1], "c": [1], "v": [1], "t": [1]},
            ProviderErrorCode.SCHEMA_MISMATCH,
        ),
        (
            {"s": "ok", "o": "bad", "h": [], "l": [], "c": [], "v": [], "t": []},
            ProviderErrorCode.SCHEMA_MISMATCH,
        ),
    ),
)
def test_candle_semantic_failures_are_not_transport_success(
    body: dict[str, object], expected: ProviderErrorCode
) -> None:
    adapter, _ = provider(Transport((response(body),)))
    result = adapter.fetch(
        request(MarketCapability.HISTORICAL_BARS_V1, ("close",)), authorization()
    )
    assert result.error is not None and result.error.code is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (401, ProviderErrorCode.AUTHENTICATION_FAILED),
        (403, ProviderErrorCode.AUTHORIZATION_FAILED),
        (429, ProviderErrorCode.RATE_LIMITED),
        (503, ProviderErrorCode.PROVIDER_UNAVAILABLE),
    ),
)
def test_provider_http_failures_are_normalized(status: int, expected: ProviderErrorCode) -> None:
    adapter, _ = provider(Transport((response({}, status),)))
    result = adapter.fetch(request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization())
    assert result.error is not None and result.error.code is expected


def test_empty_valued_ratelimit_header_is_dropped_instead_of_crashing() -> None:
    """An empty-valued *ratelimit* header must never reach ProviderResponseMetadata,
    which rejects empty quota values -- it must be dropped, not raised uncaught.
    """
    transport = Transport(
        (
            ReadOnlyHttpResponse(
                200,
                {"c": 210.25, "t": int(NOW.timestamp())},
                (("X-Ratelimit-Remaining", ""),),
                9,
                "finnhub-request-1",
            ),
        )
    )
    adapter, _ = provider(transport)
    result = adapter.fetch(request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization())
    assert result.error is None and isinstance(result.observations[0].value, Quote)


def test_entitlement_failure_is_distinct_even_on_http_200() -> None:
    adapter, _ = provider(Transport((response({"error": "Premium subscription required"}),)))
    result = adapter.fetch(
        request(MarketCapability.HISTORICAL_BARS_V1, ("close",)), authorization()
    )
    assert result.error is not None
    assert result.error.code is ProviderErrorCode.ENTITLEMENT_MISSING


@pytest.mark.parametrize(
    ("failure", "expected"),
    (
        (ReadOnlyTransportTimeout("timeout"), ProviderErrorCode.TIMEOUT),
        (ReadOnlyTransportError("transport"), ProviderErrorCode.TRANSPORT_ERROR),
    ),
)
def test_transport_failures_do_not_escape(failure: Exception, expected: ProviderErrorCode) -> None:
    adapter, _ = provider(Transport((failure,)))
    result = adapter.fetch(request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization())
    assert result.error is not None and result.error.code is expected


def test_budget_factory_registry_and_validation_framework_integration() -> None:
    transport = Transport((response({"c": 210.25, "t": int(NOW.timestamp())}),))
    config = load_market_data_config(
        {"ASA_FINNHUB_ENABLED": "true", "ASA_FINNHUB_API_KEY": "test-key"}
    )
    selected = next(item for item in config.providers if item.provider_id == "finnhub")
    budget = Budget()
    built = ProviderFactory((finnhub_provider_registration(),)).create(
        selected, ProviderDependencies(transport, Clock(), budget)
    )
    registry = ProviderRegistry((built,))
    assert registry.providers_for(MarketCapability.HISTORICAL_BARS_V1) == (built,)
    item = subject(MarketCapability.REAL_TIME_QUOTE_V1, ("last",))
    report = built.validate(
        ProviderValidationPlan(
            "finnhub-plan", "finnhub", (MarketCapability.REAL_TIME_QUOTE_V1,), 1, 1, 10, (item,)
        )
    )
    assert report.checks[0].status.value == "pass"
    assert budget.calls == [("finnhub", MarketCapability.REAL_TIME_QUOTE_V1, 1)]


def test_wrong_budget_and_write_surfaces_fail_closed() -> None:
    adapter, _ = provider(Transport((response({}),)))
    with pytest.raises(ValueError, match="budget provider mismatch"):
        adapter.fetch(
            request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization("tradier")
        )
    assert not set(FinnhubProvider.__dict__) & {
        "submit",
        "post",
        "place_order",
        "cancel",
        "modify",
        "accounts",
        "positions",
    }
