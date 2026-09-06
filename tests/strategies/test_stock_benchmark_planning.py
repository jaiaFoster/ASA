from __future__ import annotations

from datetime import UTC, datetime

from domain import DemandExpansion, MarketCapability
from strategies.stock_benchmark_planning import (
    b001_bootstrap_demands,
    b001_resolved_field_requirements,
    b002_bootstrap_demands,
    b002_resolved_field_requirements,
    no_op_expand,
)

NOW = datetime(2026, 9, 5, 15, 0, tzinfo=UTC)


def test_b001_bootstrap_demands_is_quote_only() -> None:
    demands = b001_bootstrap_demands(NOW)
    assert len(demands) == 1
    assert demands[0].capability is MarketCapability.REAL_TIME_QUOTE_V1


def test_b002_bootstrap_demands_is_quote_and_bars() -> None:
    demands = b002_bootstrap_demands(NOW)
    capabilities = {demand.capability for demand in demands}
    assert capabilities == {
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
    }


def test_no_op_expand_never_adds_a_second_phase() -> None:
    assert no_op_expand({}) == DemandExpansion()


def test_resolved_field_requirements_declare_only_what_each_benchmark_needs() -> None:
    assert set(b001_resolved_field_requirements()) == {MarketCapability.REAL_TIME_QUOTE_V1}
    assert set(b002_resolved_field_requirements()) == {
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
    }
