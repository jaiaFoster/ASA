from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from domain import MarketCapability
from strategy_runtime.adapters import build_migrated_shadow_registry


def test_option_strategies_share_exact_bootstrap_demand_identities() -> None:
    registry = build_migrated_shadow_registry(datetime(2026, 9, 23, 16, tzinfo=UTC))
    strategy_ids = ("forward_factor", "skew_momentum", "earnings_calendar")
    consumers_by_demand: dict[str, set[str]] = defaultdict(set)
    capabilities_by_demand: dict[str, MarketCapability] = {}
    declared_count = 0
    for strategy_id in strategy_ids:
        for demand in registry.binding_for(strategy_id).consumer.bootstrap_demands:
            declared_count += 1
            consumers_by_demand[demand.demand_id].add(strategy_id)
            capabilities_by_demand[demand.demand_id] = demand.capability

    assert declared_count == 10
    assert len(consumers_by_demand) == 5
    shared = {
        capability: consumers_by_demand[demand_id]
        for demand_id, capability in capabilities_by_demand.items()
        if len(consumers_by_demand[demand_id]) > 1
    }
    assert shared[MarketCapability.REAL_TIME_QUOTE_V1] == set(strategy_ids)
    assert shared[MarketCapability.OPTION_CHAIN_V1] == set(strategy_ids)
    assert shared[MarketCapability.EARNINGS_CALENDAR_V1] == {
        "forward_factor",
        "earnings_calendar",
    }


def test_option_demand_identity_is_strategy_registration_order_independent() -> None:
    registry = build_migrated_shadow_registry(datetime(2026, 9, 23, 16, tzinfo=UTC))
    orders = (
        ("forward_factor", "skew_momentum", "earnings_calendar"),
        ("earnings_calendar", "skew_momentum", "forward_factor"),
    )
    identities = []
    for order in orders:
        identities.append(
            tuple(
                sorted(
                    demand.demand_id
                    for strategy_id in order
                    for demand in registry.binding_for(strategy_id).consumer.bootstrap_demands
                )
            )
        )

    assert identities[0] == identities[1]
