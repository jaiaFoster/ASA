"""TRADIER-PATCH-002: expiration-aware option-chain subject tests.

Two layers: unit tests directly against build_capability_subject()'s new
`expiration` parameter, and one integration-level test against the real
TradierProvider class (market_data/tradier.py, unmodified) with a fake,
zero-network transport -- proving the constructed subject actually resolves
issue #156's root cause (subject.projection_for("tradier", "expiration",
...) previously always raised DomainInvariantError for every live option-
chain request), not just that the projection object looks right in
isolation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from domain import MarketCapability, OptionChain
from domain.values import DomainInvariantError
from market_data import (
    CapabilityFulfillmentService,
    FulfillmentStatus,
    ProviderDependencies,
    ProviderRegistry,
)
from market_data.config import load_market_data_config
from market_data.tradier import TradierProvider
from market_data.transport import ReadOnlyHttpResponse
from screening.live_acquisition import (
    acquire_capability,
    build_capability_registry,
    build_request_budget_manager,
)
from screening.live_context import KNOWN_PROVIDER_IDS, build_capability_subject

NOW = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
SYMBOL = "AAPL"
EXPIRATION = date(2026, 8, 21)


class TestExpirationAwareSubjectConstruction:
    def test_carries_one_expiration_projection_per_known_provider(self) -> None:
        subject = build_capability_subject(
            SYMBOL, MarketCapability.OPTION_CHAIN_V1, NOW, expiration=EXPIRATION
        )
        for provider_id in KNOWN_PROVIDER_IDS:
            projection = subject.projection_for(provider_id, "expiration", NOW)
            assert projection.address_value == EXPIRATION.isoformat()

    def test_symbol_projection_stays_explicit_and_unaffected(self) -> None:
        subject = build_capability_subject(
            SYMBOL, MarketCapability.OPTION_CHAIN_V1, NOW, expiration=EXPIRATION
        )
        projection = subject.projection_for("tradier", "symbol", NOW)
        assert projection.address_value == SYMBOL

    def test_without_expiration_no_expiration_projection_exists(self) -> None:
        # Existing symbol-only acquisitions remain unchanged -- the
        # pre-TRADIER-PATCH-002 default behavior is preserved exactly.
        subject = build_capability_subject(SYMBOL, MarketCapability.OPTION_CHAIN_V1, NOW)
        with pytest.raises(DomainInvariantError, match="one effective provider projection"):
            subject.projection_for("tradier", "expiration", NOW)

    def test_expiration_before_as_of_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="is before as_of"):
            build_capability_subject(
                SYMBOL,
                MarketCapability.OPTION_CHAIN_V1,
                NOW,
                expiration=NOW.date() - timedelta(days=1),
            )

    def test_expiration_has_no_effect_on_other_capabilities(self) -> None:
        # expiration is meaningless for a quote request -- accepted without
        # error, simply produces an otherwise-unused projection, since only
        # OPTION_CHAIN_V1 acquisition ever looks one up.
        subject = build_capability_subject(
            SYMBOL, MarketCapability.REAL_TIME_QUOTE_V1, NOW, expiration=EXPIRATION
        )
        assert subject.projection_for("tradier", "symbol", NOW).address_value == SYMBOL


class _RecordingTransport:
    """Zero-network fake ReadOnlyHttpTransport -- records every request and
    returns one canned, realistic Tradier options-chain JSON response.
    """

    def __init__(self) -> None:
        self.requests = []

    def get(self, request):  # noqa: ANN001
        self.requests.append(request)
        body = {
            "options": {
                "option": [
                    {
                        "symbol": "AAPL260821C00210000",
                        "option_type": "call",
                        "expiration_date": EXPIRATION.isoformat(),
                        "strike": 210.0,
                        "bid": 4.9,
                        "ask": 5.1,
                        "last": 5.0,
                        "volume": 1000,
                        "open_interest": 5000,
                        "underlying": SYMBOL,
                        "trade_date": "2026-07-22T16:00:00Z",
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
        return ReadOnlyHttpResponse(200, body, (), 5, "fake-tradier-ref")


def _tradier_config():
    config = load_market_data_config(
        {"ASA_TRADIER_ENABLED": "true", "ASA_TRADIER_ACCESS_TOKEN": "test-token-not-a-real-credential"}
    )
    return next(item for item in config.providers if item.provider_id == "tradier")


class _FixedClock:
    def now(self) -> datetime:
        return NOW


class TestRealTradierProviderAgainstAnExpirationAwareSubject:
    def test_tradier_receives_the_selected_expiration_as_its_query_value(self) -> None:
        """The end-to-end regression proof for issue #156: before
        TRADIER-PATCH-001/002, any real OPTION_CHAIN_V1 acquisition against
        Tradier raised DomainInvariantError before ever reaching the
        transport, because no subject carried an "expiration" projection.
        This exercises the real, unmodified TradierProvider against a fake
        transport and confirms the request actually goes out with the
        selected expiration in its query string.
        """
        clock = _FixedClock()
        transport = _RecordingTransport()
        config = _tradier_config()
        budget_manager = build_request_budget_manager((config,), clock)
        provider = TradierProvider(config, ProviderDependencies(transport, clock, budget_manager))
        registry = ProviderRegistry((provider,))
        capability_registry = build_capability_registry(registry)
        fulfillment = CapabilityFulfillmentService(registry, capability_registry, budget_manager)

        subject = build_capability_subject(
            SYMBOL, MarketCapability.OPTION_CHAIN_V1, NOW, expiration=EXPIRATION
        )
        result = acquire_capability(
            fulfillment,
            MarketCapability.OPTION_CHAIN_V1,
            subject,
            effective_start=NOW,
            effective_end=NOW,
            required_fields=("contracts",),
            maximum_age_seconds=3600,
        )

        assert result.status is FulfillmentStatus.FULFILLED
        (observation,) = result.observations
        assert isinstance(observation.value, OptionChain)
        assert observation.value.contracts[0].expiration == EXPIRATION

        (sent_request,) = transport.requests
        assert ("expiration", EXPIRATION.isoformat()) in sent_request.query
        assert ("symbol", SYMBOL) in sent_request.query
