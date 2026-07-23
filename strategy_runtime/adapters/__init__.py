"""Migrated strategy adapters (SPRINT-009/EPIC-7).

One module per migrated strategy: forward_factor, skew_momentum_vertical,
earnings_calendar. Each declares its own StrategyContract (EPIC-2) and a
StrategyAdapter (EPIC-1) that reuses the existing, unmodified execution
graph (screening.live_adapters, strategies/stonk_manifests.py --
this sprint's own quality.preserve rule for "execution graph") and
translates its ScreeningResult into this sprint's UniversalScreeningResult
(EPIC-6) via _screening_bridge.translate_screening_result(), the one
translation rule every migrated strategy shares.

build_migrated_strategy_registry() (EPIC-9) is the one place all three
are actually registered together -- wiring that registry into the
deployed API's own route handlers remains a separate, deliberately
deferred step (see project/reports/SPRINT-009.md); importing this
subpackage has no side effect on the currently-shipped
/api/v1/screening* surface on its own.
"""

from __future__ import annotations

from strategy_runtime.adapters.earnings_calendar import (
    EARNINGS_CALENDAR_CONTRACT,
    earnings_calendar_adapter,
)
from strategy_runtime.adapters.forward_factor import (
    FORWARD_FACTOR_CONTRACT,
    forward_factor_adapter,
)
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
    skew_momentum_adapter,
)
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult

__all__ = ["build_migrated_strategy_registry"]


def build_migrated_strategy_registry() -> StrategyRegistry[UniversalScreeningResult]:
    """All three EPIC-7 migration targets, registered together -- the one
    place this sprint's own "three production strategies execute through
    one shared runtime" success criterion is assembled and directly
    checkable (see tests/strategy_runtime/adapters/test_registry.py).
    """
    return StrategyRegistry(
        (
            (FORWARD_FACTOR_CONTRACT, forward_factor_adapter),
            (SKEW_MOMENTUM_VERTICAL_CONTRACT, skew_momentum_adapter),
            (EARNINGS_CALENDAR_CONTRACT, earnings_calendar_adapter),
        )
    )
