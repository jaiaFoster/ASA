"""Migrated strategy adapters (SPRINT-009/EPIC-7).

One module per migrated strategy: forward_factor, skew_momentum_vertical,
earnings_calendar. Each declares its own StrategyContract (EPIC-2) and a
StrategyAdapter (EPIC-1) that reuses the existing, unmodified execution
graph (screening.live_adapters, strategies/stonk_manifests.py --
this sprint's own quality.preserve rule for "execution graph") and
translates its ScreeningResult into this sprint's UniversalScreeningResult
(EPIC-6) via _screening_bridge.translate_screening_result(), the one
translation rule every migrated strategy shares.

Registering these adapters with a real strategy_runtime.StrategyRegistry
and wiring that registry into the deployed API is EPIC-9's own job, not
this package's -- importing this subpackage has no side effect on the
currently-shipped /api/v1/screening* surface.
"""

from __future__ import annotations
