"""S14R: migrated read-only adapters cannot regain acquisition authority."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = (
    ROOT / "strategy_runtime/adapters/earnings_calendar_subject_first.py",
    ROOT / "strategy_runtime/adapters/forward_factor_subject_first.py",
    ROOT / "strategy_runtime/adapters/skew_momentum_subject_first.py",
    ROOT / "strategy_runtime/adapters/stock_benchmarks_subject_first.py",
    ROOT / "strategy_runtime/adapters/zhan_subject_first.py",
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
        "B001",
        "B002",
        "earnings_calendar",
        "event_vol_gxz_preea_straddle_to_expiry",
        "forward_factor",
        "index_buywrite_cboe_bxm",
        "index_putwrite_cboe_put",
        "index_putwrite_cboe_puty",
        "index_short_vol_scs_near_atm_straddle",
        "skew_momentum",
        "spy_put_credit_spread",
        "xs_option_heston_straddle_momentum_lowcost",
        "xs_option_zhan_neg_lnprice_dn_call",
    )
