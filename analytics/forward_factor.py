"""Forward Factor derived analytics (ANALYTICS-002).

Implements the two derived features SPRINT-006 found missing from this
codebase: per-contract implied volatility extraction and days-to-expiration
computation, ready to feed the existing, frozen Forward Factor manifest's
implied_forward_volatility node (front_iv/back_iv/front_dte/back_dte)
without any further calculation. Deliberately does NOT reimplement that
node's own forward-variance blending formula
(strategies/stonk_components.py::ImpliedForwardVolatility) -- it already
exists, is already correct, and duplicating it here would only risk drift.

implied_volatility is read directly from the canonical
domain.OptionContract field the Market Data Platform already populates from
the live provider (see market_data/tradier.py) -- no Black-Scholes solving
is implemented or needed here.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import cast

from domain import MarketCapability, OptionChain, OptionType
from analytics.engine import FeatureComputation
from analytics.errors import MissingImpliedVolatilityError, NoMatchingContractError
from analytics.registry import AnalyticsFeatureDefinition, AnalyticsRegistry

DAYS_TO_EXPIRATION_FEATURE_ID = "days_to_expiration"
OPTION_IMPLIED_VOLATILITY_FEATURE_ID = "option_implied_volatility"


def compute_days_to_expiration(inputs: Mapping[str, object]) -> Decimal:
    expiration = cast(date, inputs["expiration"])
    as_of = cast(date, inputs["as_of"])
    if expiration < as_of:
        raise ValueError("expiration cannot precede as_of")
    return Decimal((expiration - as_of).days)


def compute_option_implied_volatility(inputs: Mapping[str, object]) -> Decimal:
    chain = cast(OptionChain, inputs["chain"])
    expiration = cast(date, inputs["expiration"])
    strike = cast(Decimal, inputs["strike"])
    option_type = cast(OptionType, inputs["option_type"])
    matches = chain.find(expiration=expiration, strike=strike, option_type=option_type)
    if not matches:
        raise NoMatchingContractError(expiration.isoformat(), str(strike))
    contract = matches[0]
    if contract.implied_volatility is None:
        raise MissingImpliedVolatilityError(expiration.isoformat(), str(strike))
    return contract.implied_volatility


FORWARD_FACTOR_ANALYTICS_DEFINITIONS: tuple[AnalyticsFeatureDefinition, ...] = (
    AnalyticsFeatureDefinition(
        DAYS_TO_EXPIRATION_FEATURE_ID,
        "1.0.0",
        "Calendar days between as_of and a given expiration date.",
        (MarketCapability.OPTION_CHAIN_V1,),
    ),
    AnalyticsFeatureDefinition(
        OPTION_IMPLIED_VOLATILITY_FEATURE_ID,
        "1.0.0",
        "Canonical implied_volatility of the option contract matching an "
        "expiration/strike/type, as already reported by the Market Data Platform.",
        (MarketCapability.OPTION_CHAIN_V1,),
    ),
)

FORWARD_FACTOR_ANALYTICS_REGISTRY = AnalyticsRegistry(FORWARD_FACTOR_ANALYTICS_DEFINITIONS)

FORWARD_FACTOR_ANALYTICS_COMPUTATIONS: dict[str, FeatureComputation] = {
    DAYS_TO_EXPIRATION_FEATURE_ID: compute_days_to_expiration,
    OPTION_IMPLIED_VOLATILITY_FEATURE_ID: compute_option_implied_volatility,
}
