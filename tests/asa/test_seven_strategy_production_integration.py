"""SP-07A anti-shelving proof for all seven research-selected strategies."""

from datetime import UTC, datetime

from asa.scheduled_screening import (
    FIXED_SUBJECT_OPTION_UNIVERSE,
    PRODUCTION_SCREENING_UNIVERSE,
)
from strategy_runtime.adapters import (
    build_migrated_cutover_policy,
    build_migrated_shadow_registry,
    build_migrated_signal_catalog,
    build_migrated_strategy_registry,
)

SELECTED = frozenset(
    {
        "event_vol_gxz_preea_straddle_to_expiry",
        "index_putwrite_cboe_put",
        "index_putwrite_cboe_puty",
        "index_short_vol_scs_near_atm_straddle",
        "xs_option_zhan_neg_lnprice_dn_call",
        "xs_option_heston_straddle_momentum_lowcost",
        "index_buywrite_cboe_bxm",
    }
)


def test_all_seven_are_registered_cataloged_bound_and_cut_over() -> None:
    now = datetime(2026, 10, 16, 21, tzinfo=UTC)
    registry = build_migrated_strategy_registry()
    shadows = build_migrated_shadow_registry(now)
    catalog = build_migrated_signal_catalog()
    policy = build_migrated_cutover_policy({})
    assert set(registry.strategy_ids()) >= SELECTED
    assert set(shadows.strategy_ids()) >= SELECTED
    assert {item.signal_id for item in catalog} >= SELECTED
    assert all(policy.is_cut_over(strategy_id) for strategy_id in SELECTED)


def test_all_seven_have_normal_scheduled_production_paths() -> None:
    cohort_ids = {strategy_id for strategy_id, _symbol in PRODUCTION_SCREENING_UNIVERSE}
    fixed_pairs = set(FIXED_SUBJECT_OPTION_UNIVERSE)
    assert {
        "event_vol_gxz_preea_straddle_to_expiry",
        "xs_option_zhan_neg_lnprice_dn_call",
        "xs_option_heston_straddle_momentum_lowcost",
    } <= cohort_ids
    assert {
        ("index_putwrite_cboe_put", "SPX"),
        ("index_putwrite_cboe_puty", "SPX"),
        ("index_short_vol_scs_near_atm_straddle", "SPX"),
        ("index_buywrite_cboe_bxm", "SPX"),
    } <= fixed_pairs
