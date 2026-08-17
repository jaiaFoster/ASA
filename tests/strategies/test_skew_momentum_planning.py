from datetime import UTC, datetime

from domain import MarketCapability
from strategies.skew_momentum_planning import bars_demand, resolved_field_requirements


def test_historical_bars_demand_matches_resolution_freshness_policy() -> None:
    demand = bars_demand(datetime(2026, 8, 17, 20, 30, tzinfo=UTC))
    _fields, maximum_age_seconds = resolved_field_requirements()[
        MarketCapability.HISTORICAL_BARS_V1
    ]

    assert demand.maximum_age_seconds == maximum_age_seconds
