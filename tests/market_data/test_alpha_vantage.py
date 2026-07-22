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
from market_data.alpha_vantage import AlphaVantageProvider, alpha_vantage_provider_registration
from market_data.providers import ProviderErrorCode
from market_data.transport import ReadOnlyHttpRequest, ReadOnlyHttpResponse

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
        self.calls = 0

    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        self.calls += 1
        return RequestBudgetAuthorization("validation", provider_id, request_units, 1)


class Transport:
    def __init__(self, responses: tuple[ReadOnlyHttpResponse, ...]) -> None:
        self.responses = list(responses)
        self.requests: list[ReadOnlyHttpRequest] = []

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def response(body: dict[str, object], status: int = 200) -> ReadOnlyHttpResponse:
    return ReadOnlyHttpResponse(status, body, (), 15, "alpha-request-1")


def subject(capability: MarketCapability, fields: tuple[str, ...]) -> MarketDataSubject:
    projection = ProviderAddressProjection(
        "alpha_vantage", "v1", "symbol", "AAPL", NOW - timedelta(days=180), None, EVIDENCE
    )
    kind = (
        MarketDataSubjectType.EARNINGS_SECURITY
        if capability is MarketCapability.EARNINGS_CALENDAR_V1
        else MarketDataSubjectType.INSTRUMENT
    )
    return MarketDataSubject(
        INSTRUMENT,
        kind,
        capability,
        MarketDataRequestContext(NOW - timedelta(days=120), NOW, fields, (projection,), EVIDENCE),
    )


def request(capability: MarketCapability, fields: tuple[str, ...]) -> CapabilityRequest:
    item = subject(capability, fields)
    return CapabilityRequest(
        capability,
        (item,),
        item.request_context.semantic_start,
        item.request_context.semantic_end,
        fields,
        86400 * 180,
    )


def provider(
    transport: Transport, budget: Budget | None = None
) -> tuple[AlphaVantageProvider, Budget]:
    config = load_market_data_config(
        {"ASA_ALPHA_VANTAGE_ENABLED": "true", "ASA_ALPHA_VANTAGE_API_KEY": "test-key"}
    )
    selected = next(item for item in config.providers if item.provider_id == "alpha_vantage")
    authorizer = budget or Budget()
    return AlphaVantageProvider(
        selected, ProviderDependencies(transport, Clock(), authorizer)
    ), authorizer


def authorization(provider_id: str = "alpha_vantage") -> RequestBudgetAuthorization:
    return RequestBudgetAuthorization("budget", provider_id, 1, 1)


def test_daily_bars_use_compact_raw_documented_endpoint_and_decimal_values() -> None:
    body = {
        "Time Series (Daily)": {
            "2026-07-20": {
                "1. open": "205.00",
                "2. high": "212",
                "3. low": "204",
                "4. close": "210",
                "5. volume": "50000000",
            }
        }
    }
    transport = Transport((response(body),))
    adapter, _ = provider(transport)
    result = adapter.fetch(
        request(MarketCapability.HISTORICAL_BARS_V1, ("open", "high", "low", "close", "volume")),
        authorization(),
    )
    assert result.error is None and isinstance(result.observations[0].value, OHLCVBar)
    query = dict(transport.requests[0].query)
    assert query["function"] == "TIME_SERIES_DAILY" and query["outputsize"] == "compact"
    assert "test-key" not in repr(transport.requests[0])


def test_quarterly_earnings_json_normalizes_reported_event() -> None:
    body = {
        "quarterlyEarnings": [
            {"fiscalDateEnding": "2026-06-30", "reportedDate": "2026-07-10", "reportedEPS": "1.50"}
        ]
    }
    adapter, _ = provider(Transport((response(body),)))
    result = adapter.fetch(
        request(MarketCapability.EARNINGS_CALENDAR_V1, ("earnings_date",)), authorization()
    )
    assert result.error is None and isinstance(result.observations[0].value, EarningsEvent)


@pytest.mark.parametrize(
    ("body", "expected"),
    (
        ({"Note": "request frequency exceeded"}, ProviderErrorCode.RATE_LIMITED),
        ({"Information": "API rate limit reached"}, ProviderErrorCode.RATE_LIMITED),
        ({"Information": "premium subscription required"}, ProviderErrorCode.ENTITLEMENT_MISSING),
        ({"Error Message": "Invalid API key"}, ProviderErrorCode.AUTHENTICATION_FAILED),
        ({"Error Message": "Invalid API call"}, ProviderErrorCode.INVALID_REQUEST),
        ({}, ProviderErrorCode.EMPTY_PAYLOAD),
    ),
)
def test_message_and_empty_payloads_are_never_market_data(
    body: dict[str, object], expected: ProviderErrorCode
) -> None:
    adapter, _ = provider(Transport((response(body),)))
    result = adapter.fetch(
        request(MarketCapability.HISTORICAL_BARS_V1, ("close",)), authorization()
    )
    assert result.error is not None and result.error.code is expected


def test_malformed_schema_and_no_rows_in_requested_window_fail_closed() -> None:
    malformed, _ = provider(Transport((response({"Time Series (Daily)": {"2026-07-20": "bad"}}),)))
    result = malformed.fetch(
        request(MarketCapability.HISTORICAL_BARS_V1, ("close",)), authorization()
    )
    assert result.error is not None and result.error.code is ProviderErrorCode.SCHEMA_MISMATCH
    old, _ = provider(
        Transport((response({"Time Series (Daily)": {"2020-01-01": {"1. open": 1}}}),))
    )
    result = old.fetch(request(MarketCapability.HISTORICAL_BARS_V1, ("close",)), authorization())
    assert result.error is not None and result.error.code is ProviderErrorCode.NO_DATA


def test_factory_registry_budget_validation_and_read_only_surface() -> None:
    transport = Transport(
        (
            response(
                {
                    "Time Series (Daily)": {
                        "2026-07-20": {
                            "1. open": 205,
                            "2. high": 212,
                            "3. low": 204,
                            "4. close": 210,
                            "5. volume": 5,
                        }
                    }
                }
            ),
        )
    )
    config = load_market_data_config(
        {"ASA_ALPHA_VANTAGE_ENABLED": "true", "ASA_ALPHA_VANTAGE_API_KEY": "key"}
    )
    selected = next(item for item in config.providers if item.provider_id == "alpha_vantage")
    budget = Budget()
    built = ProviderFactory((alpha_vantage_provider_registration(),)).create(
        selected, ProviderDependencies(transport, Clock(), budget)
    )
    assert ProviderRegistry((built,)).providers_for(MarketCapability.HISTORICAL_BARS_V1) == (built,)
    item = subject(MarketCapability.HISTORICAL_BARS_V1, ("close",))
    report = built.validate(
        ProviderValidationPlan(
            "plan", "alpha_vantage", (MarketCapability.HISTORICAL_BARS_V1,), 1, 1, 10, (item,)
        )
    )
    assert report.checks[0].status.value == "pass" and budget.calls == 1
    assert not set(AlphaVantageProvider.__dict__) & {
        "submit",
        "post",
        "place_order",
        "cancel",
        "modify",
        "accounts",
    }


def test_wrong_budget_fails_before_transport() -> None:
    adapter, _ = provider(Transport((response({}),)))
    with pytest.raises(ValueError, match="budget provider mismatch"):
        adapter.fetch(
            request(MarketCapability.HISTORICAL_BARS_V1, ("close",)), authorization("finnhub")
        )
