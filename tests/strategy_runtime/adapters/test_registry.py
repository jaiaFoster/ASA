"""SPRINT-009/EPIC-9: all three EPIC-7 migration targets registered
together -- directly checking this sprint's own "three production
strategies execute through one shared runtime" success criterion. Extended
by STOCK-RUNTIME-001 STK-03: B001/B002 join the same shared registry
without disturbing the original three's own identities.
"""

from __future__ import annotations

from strategy_runtime.adapters import build_migrated_strategy_registry


def test_all_three_migration_targets_are_registered() -> None:
    registry = build_migrated_strategy_registry()
    assert registry.strategy_ids() == (
        "B001",
        "B002",
        "earnings_calendar",
        "forward_factor",
        "skew_momentum",
    )


def test_each_registered_strategy_has_a_contract_and_an_adapter() -> None:
    registry = build_migrated_strategy_registry()
    for strategy_id in registry.strategy_ids():
        contract = registry.contract_for(strategy_id)
        assert contract.strategy_id == strategy_id
        assert callable(registry.adapter_for(strategy_id))
