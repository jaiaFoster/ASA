from __future__ import annotations

from datetime import timedelta

import pytest

from domain import MarketCapability
from domain.values import DomainInvariantError
from market_data import ProviderCapabilityCase, evaluate_provider_compliance
from tests.market_data import test_alpha_vantage as alpha
from tests.market_data import test_finnhub as finnhub
from tests.market_data import test_tradier as tradier
from tests.market_data.test_fixture_provider import budget as fixture_budget
from tests.market_data.test_fixture_provider import provider as fixture_provider
from tests.market_data.test_fixture_provider import request as fixture_request


def test_tradier_passes_shared_supported_capability_suite() -> None:
    quote = tradier.provider(
        tradier.Transport(
            (
                tradier.response(
                    {"quotes": {"quote": {"symbol": "AAPL", "last": 210, "bid": 209, "ask": 211}}}
                ),
            )
        )
    )
    bars = tradier.provider(
        tradier.Transport(
            (
                tradier.response(
                    {
                        "history": {
                            "day": [
                                {
                                    "date": "2026-07-20",
                                    "open": 205,
                                    "high": 212,
                                    "low": 204,
                                    "close": 210,
                                    "volume": 50,
                                }
                            ]
                        }
                    }
                ),
            )
        )
    )
    chain = tradier.provider(
        tradier.Transport(
            (
                tradier.response(
                    {
                        "options": {
                            "option": [
                                {
                                    "symbol": "AAPL260821C00210000",
                                    "underlying": "AAPL",
                                    "expiration_date": "2026-08-21",
                                    "strike": 210,
                                    "option_type": "call",
                                    "bid": 4,
                                    "ask": 5,
                                    "last": 4.5,
                                    "volume": 10,
                                    "open_interest": 20,
                                    "greeks": {
                                        "delta": 0.5,
                                        "gamma": 0.03,
                                        "theta": -0.1,
                                        "vega": 0.2,
                                        "rho": 0.01,
                                        "mid_iv": 0.25,
                                    },
                                }
                            ]
                        }
                    }
                ),
            )
        )
    )
    cases = (
        ProviderCapabilityCase(
            MarketCapability.REAL_TIME_QUOTE_V1,
            quote.fetch(
                tradier.request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)),
                tradier.authorization(),
            ),
        ),
        ProviderCapabilityCase(
            MarketCapability.HISTORICAL_BARS_V1,
            bars.fetch(
                tradier.request(
                    MarketCapability.HISTORICAL_BARS_V1, ("open", "high", "low", "close", "volume")
                ),
                tradier.authorization(),
            ),
        ),
        ProviderCapabilityCase(
            MarketCapability.OPTION_CHAIN_V1,
            chain.fetch(
                tradier.request(
                    MarketCapability.OPTION_CHAIN_V1,
                    ("contracts", "greeks", "implied_volatility", "volume", "open_interest"),
                    expiration=True,
                ),
                tradier.authorization(),
            ),
        ),
    )
    assert evaluate_provider_compliance(quote, cases).passed


def test_finnhub_passes_shared_supported_capability_suite() -> None:
    stamp = int((finnhub.NOW - timedelta(days=2)).timestamp())
    quote, _ = finnhub.provider(
        finnhub.Transport((finnhub.response({"c": 210, "t": int(finnhub.NOW.timestamp())}),))
    )
    bars, _ = finnhub.provider(
        finnhub.Transport(
            (
                finnhub.response(
                    {
                        "s": "ok",
                        "o": [205],
                        "h": [212],
                        "l": [204],
                        "c": [210],
                        "v": [50],
                        "t": [stamp],
                    }
                ),
            )
        )
    )
    earnings, _ = finnhub.provider(
        finnhub.Transport(
            (
                finnhub.response(
                    {"earningsCalendar": [{"symbol": "AAPL", "date": "2026-08-01", "hour": "amc"}]}
                ),
            )
        )
    )
    cases = (
        ProviderCapabilityCase(
            MarketCapability.REAL_TIME_QUOTE_V1,
            quote.fetch(
                finnhub.request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)),
                finnhub.authorization(),
            ),
        ),
        ProviderCapabilityCase(
            MarketCapability.HISTORICAL_BARS_V1,
            bars.fetch(
                finnhub.request(
                    MarketCapability.HISTORICAL_BARS_V1, ("open", "high", "low", "close", "volume")
                ),
                finnhub.authorization(),
            ),
        ),
        ProviderCapabilityCase(
            MarketCapability.EARNINGS_CALENDAR_V1,
            earnings.fetch(
                finnhub.request(MarketCapability.EARNINGS_CALENDAR_V1, ("earnings_date",)),
                finnhub.authorization(),
            ),
        ),
    )
    assert evaluate_provider_compliance(quote, cases).passed


def test_alpha_vantage_passes_shared_supported_capability_suite() -> None:
    bars, _ = alpha.provider(
        alpha.Transport(
            (
                alpha.response(
                    {
                        "Time Series (Daily)": {
                            "2026-07-20": {
                                "1. open": "205",
                                "2. high": "212",
                                "3. low": "204",
                                "4. close": "210",
                                "5. volume": "50",
                            }
                        }
                    }
                ),
            )
        )
    )
    earnings, _ = alpha.provider(
        alpha.Transport(
            (
                alpha.response(
                    {
                        "quarterlyEarnings": [
                            {
                                "fiscalDateEnding": "2026-06-30",
                                "reportedDate": "2026-07-10",
                                "reportedEPS": "1.5",
                            }
                        ]
                    }
                ),
            )
        )
    )
    cases = (
        ProviderCapabilityCase(
            MarketCapability.HISTORICAL_BARS_V1,
            bars.fetch(
                alpha.request(
                    MarketCapability.HISTORICAL_BARS_V1, ("open", "high", "low", "close", "volume")
                ),
                alpha.authorization(),
            ),
        ),
        ProviderCapabilityCase(
            MarketCapability.EARNINGS_CALENDAR_V1,
            earnings.fetch(
                alpha.request(MarketCapability.EARNINGS_CALENDAR_V1, ("earnings_date",)),
                alpha.authorization(),
            ),
        ),
    )
    assert evaluate_provider_compliance(bars, cases).passed


def test_fixture_provider_passes_every_declared_capability() -> None:
    provider = fixture_provider()
    fields = {
        MarketCapability.REAL_TIME_QUOTE_V1: ("last",),
        MarketCapability.HISTORICAL_BARS_V1: ("open", "close"),
        MarketCapability.OPTION_CHAIN_V1: (
            "contracts",
            "greeks",
            "implied_volatility",
            "volume",
            "open_interest",
        ),
        MarketCapability.EARNINGS_CALENDAR_V1: ("earnings_date",),
    }
    cases = tuple(
        ProviderCapabilityCase(
            capability,
            provider.fetch(fixture_request(capability, fields[capability]), fixture_budget()),
        )
        for capability in provider.capabilities
    )
    assert evaluate_provider_compliance(provider, cases).passed


def test_compliance_fails_when_claimed_capability_lacks_coverage() -> None:
    provider = fixture_provider()
    with pytest.raises(DomainInvariantError, match="every declared capability"):
        evaluate_provider_compliance(provider, ())
