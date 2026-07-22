from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    OHLCVBar,
    OptionChain,
    ProviderAddressProjection,
    Quote,
)
from market_data import (
    CapabilityRequest,
    ProviderDependencies,
    RequestBudgetAuthorization,
    load_market_data_config,
)
from market_data.providers import ProviderErrorCode
from market_data.tradier import TradierProvider
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
    def authorize(
        self, provider_id: str, capability: MarketCapability, request_units: int
    ) -> RequestBudgetAuthorization:
        return RequestBudgetAuthorization("validation-budget", provider_id, request_units, 1)


class Transport:
    def __init__(self, responses: tuple[ReadOnlyHttpResponse, ...]) -> None:
        self.responses = list(responses)
        self.requests: list[ReadOnlyHttpRequest] = []

    def get(self, request: ReadOnlyHttpRequest) -> ReadOnlyHttpResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def response(body: dict[str, object], status: int = 200) -> ReadOnlyHttpResponse:
    return ReadOnlyHttpResponse(
        status, body, (("X-Ratelimit-Available", "119"),), 12, "tradier-request-1"
    )


def subject(
    capability: MarketCapability, fields: tuple[str, ...], *, expiration: bool = False
) -> MarketDataSubject:
    projections = [
        ProviderAddressProjection(
            "tradier", "v1", "symbol", "AAPL", NOW - timedelta(days=30), None, EVIDENCE
        )
    ]
    if expiration:
        projections.append(
            ProviderAddressProjection(
                "tradier",
                "v1",
                "expiration",
                "2026-08-21",
                NOW - timedelta(days=30),
                None,
                EVIDENCE,
            )
        )
    kind = {MarketCapability.OPTION_CHAIN_V1: MarketDataSubjectType.OPTION_UNDERLYING}.get(
        capability, MarketDataSubjectType.INSTRUMENT
    )
    return MarketDataSubject(
        INSTRUMENT,
        kind,
        capability,
        MarketDataRequestContext(
            NOW - timedelta(days=5), NOW, fields, tuple(projections), EVIDENCE
        ),
    )


def request(
    capability: MarketCapability, fields: tuple[str, ...], *, expiration: bool = False
) -> CapabilityRequest:
    item = subject(capability, fields, expiration=expiration)
    return CapabilityRequest(
        capability,
        (item,),
        item.request_context.semantic_start,
        item.request_context.semantic_end,
        fields,
        86400 * 10,
    )


def provider(transport: Transport) -> TradierProvider:
    config = load_market_data_config(
        {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "test-token"}
    )
    tradier = next(item for item in config.providers if item.provider_id == "tradier")
    return TradierProvider(tradier, ProviderDependencies(transport, Clock(), Budget()))


def authorization() -> RequestBudgetAuthorization:
    return RequestBudgetAuthorization("budget", "tradier", 1, 1)


def test_quote_normalization_uses_only_read_market_endpoint_and_redacts_repr() -> None:
    transport = Transport(
        (
            response(
                {
                    "quotes": {
                        "quote": {
                            "symbol": "AAPL",
                            "bid": 209.9,
                            "ask": 210.1,
                            "last": 210,
                            "bidsize": 100,
                            "asksize": 120,
                            "volume": 1000000,
                        }
                    }
                }
            ),
        )
    )
    result = provider(transport).fetch(
        request(MarketCapability.REAL_TIME_QUOTE_V1, ("bid", "ask", "last")), authorization()
    )
    assert result.error is None and isinstance(result.observations[0].value, Quote)
    assert transport.requests[0].path == "/v1/markets/quotes"
    assert transport.requests[0].query == (("greeks", "false"), ("symbols", "AAPL"))
    assert "test-token" not in repr(transport.requests[0])


def test_daily_history_normalizes_decimal_ohlcv() -> None:
    transport = Transport(
        (
            response(
                {
                    "history": {
                        "day": [
                            {
                                "date": "2026-07-20",
                                "open": "205.00",
                                "high": "212",
                                "low": "204",
                                "close": "210",
                                "volume": 50000000,
                            }
                        ]
                    }
                }
            ),
        )
    )
    result = provider(transport).fetch(
        request(MarketCapability.HISTORICAL_BARS_V1, ("open", "high", "low", "close", "volume")),
        authorization(),
    )
    assert result.error is None and isinstance(result.observations[0].value, OHLCVBar)
    assert transport.requests[0].path == "/v1/markets/history"


def test_option_chain_preserves_greeks_iv_and_liquidity() -> None:
    row = {
        "symbol": "AAPL260821C00210000",
        "underlying": "AAPL",
        "expiration_date": "2026-08-21",
        "strike": "210",
        "option_type": "call",
        "bid": "4.9",
        "ask": "5.1",
        "last": "5",
        "volume": 1000,
        "open_interest": 5000,
        "greeks": {
            "delta": "0.5",
            "gamma": "0.03",
            "theta": "-0.1",
            "vega": "0.2",
            "rho": "0.01",
            "mid_iv": "0.25",
        },
    }
    transport = Transport((response({"options": {"option": [row]}}),))
    fields = ("contracts", "greeks", "implied_volatility", "volume", "open_interest")
    result = provider(transport).fetch(
        request(MarketCapability.OPTION_CHAIN_V1, fields, expiration=True), authorization()
    )
    chain = result.observations[0].value
    assert isinstance(chain, OptionChain) and chain.contracts[0].delta is not None
    assert result.observations[0].completeness.missing_fields == ()
    assert transport.requests[0].path == "/v1/markets/options/chains"


@pytest.mark.parametrize(
    ("status", "code"),
    (
        (401, ProviderErrorCode.AUTHENTICATION_FAILED),
        (403, ProviderErrorCode.ENTITLEMENT_MISSING),
        (429, ProviderErrorCode.RATE_LIMITED),
        (503, ProviderErrorCode.PROVIDER_UNAVAILABLE),
    ),
)
def test_http_failures_are_normalized(status: int, code: ProviderErrorCode) -> None:
    result = provider(Transport((response({}, status),))).fetch(
        request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization()
    )
    assert result.error is not None and result.error.code is code


def test_malformed_and_empty_payloads_fail_closed() -> None:
    malformed = provider(Transport((response({"quotes": {"quote": {"last": "bad"}}}),))).fetch(
        request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization()
    )
    assert malformed.error is not None and malformed.error.code is ProviderErrorCode.SCHEMA_MISMATCH
    empty = provider(Transport((response({"quotes": {"quote": None}}),))).fetch(
        request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization()
    )
    assert empty.error is not None and empty.error.code is ProviderErrorCode.EMPTY_PAYLOAD


def test_adapter_has_no_write_or_brokerage_surface() -> None:
    names = set(TradierProvider.__dict__)
    assert not names & {
        "submit",
        "post",
        "place_order",
        "cancel",
        "modify",
        "accounts",
        "positions",
    }
