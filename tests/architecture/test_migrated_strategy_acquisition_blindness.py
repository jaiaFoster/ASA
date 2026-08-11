"""S14R: migrated read-only adapters cannot regain acquisition authority."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = (
    ROOT / "strategy_runtime/adapters/earnings_calendar_subject_first.py",
    ROOT / "strategy_runtime/adapters/forward_factor_subject_first.py",
    ROOT / "strategy_runtime/adapters/skew_momentum_subject_first.py",
)
FORBIDDEN = {
    "CapabilityFulfiller",
    "CapabilityFulfillmentService",
    "BudgetManager",
    "Provider",
    "CapabilityRequest",
}


def test_migrated_read_only_adapters_import_no_acquisition_authority() -> None:
    for path in ADAPTERS:
        tree = ast.parse(path.read_text())
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert imported.isdisjoint(FORBIDDEN), path


def test_all_production_strategies_have_subject_first_bindings() -> None:
    from datetime import UTC, datetime

    from strategy_runtime.adapters import build_migrated_shadow_registry

    registry = build_migrated_shadow_registry(datetime(2026, 8, 11, tzinfo=UTC))
    assert registry.strategy_ids() == (
        "earnings_calendar",
        "forward_factor",
        "skew_momentum",
    )
