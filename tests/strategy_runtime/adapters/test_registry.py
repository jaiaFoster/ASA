"""SPRINT-009/EPIC-9: all three EPIC-7 migration targets registered
together -- directly checking this sprint's own "three production
strategies execute through one shared runtime" success criterion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from strategy_runtime.adapters import build_migrated_strategy_registry
from strategy_runtime.adapters.earnings_calendar import EARNINGS_CALENDAR_CONTRACT
from strategy_runtime.context import RuntimeContext


@dataclass
class _FixedClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


def test_all_three_migration_targets_are_registered() -> None:
    registry = build_migrated_strategy_registry()
    assert registry.strategy_ids() == ("earnings_calendar", "forward_factor", "skew_momentum")


def test_each_registered_strategy_has_a_contract_and_an_adapter() -> None:
    registry = build_migrated_strategy_registry()
    for strategy_id in registry.strategy_ids():
        contract = registry.contract_for(strategy_id)
        assert contract.strategy_id == strategy_id
        assert callable(registry.adapter_for(strategy_id))


class TestEarningsCalendarCutoverSwitch:
    """SPRINT-014 S14-PR-05's own required rollback switch. Each adapter's
    own missing-dependency guard raises a distinct, existing message
    (RuntimeContext.sealed_evidence is None -- the new sealed path;
    fulfillment is None -- the legacy path) -- calling the registered
    adapter with neither sealed_evidence nor legacy fulfillment supplied
    and asserting *which* message comes back proves which code path the
    switch actually selected, deterministically, without needing a full
    live acquisition fixture for either path.
    """

    def test_cutover_enabled_by_default_selects_the_sealed_evidence_path(self) -> None:
        registry = build_migrated_strategy_registry()
        context = RuntimeContext(
            EARNINGS_CALENDAR_CONTRACT, "AAPL", _FixedClock(datetime.now(UTC)), "run-1"
        )
        with pytest.raises(RuntimeError, match="sealed subject-first evidence"):
            registry.adapter_for("earnings_calendar")(context)

    def test_cutover_disabled_selects_the_legacy_acquisition_path(self) -> None:
        registry = build_migrated_strategy_registry(earnings_calendar_cutover_enabled=False)
        context = RuntimeContext(
            EARNINGS_CALENDAR_CONTRACT, "AAPL", _FixedClock(datetime.now(UTC)), "run-1"
        )
        with pytest.raises(RuntimeError, match="legacy path.*requires shared market data access"):
            registry.adapter_for("earnings_calendar")(context)

    def test_cutover_disabled_still_registers_all_three_targets(self) -> None:
        registry = build_migrated_strategy_registry(earnings_calendar_cutover_enabled=False)
        assert registry.strategy_ids() == ("earnings_calendar", "forward_factor", "skew_momentum")
