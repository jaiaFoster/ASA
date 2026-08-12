"""SPRINT-014 S14-PR-05, Architect checkpoint: nineteenth review
("CUTOVER_PASS ... implement the already-approved PR-05 cutover
mechanism") -- build_migrated_cutover_policy()'s own environment-boundary
parsing, in isolation from refresh_with_shadow()'s own dispatch mechanics
(covered by tests/strategy_runtime/test_orchestration.py's own
TestCutoverDispatch).
"""

from __future__ import annotations

from strategy_runtime.adapters import build_migrated_cutover_policy
from strategy_runtime.adapters.earnings_calendar import EARNINGS_CALENDAR_CONTRACT


def test_absent_flag_defaults_to_subject_first_authority() -> None:
    policy = build_migrated_cutover_policy({})
    assert policy.is_cut_over(EARNINGS_CALENDAR_CONTRACT.strategy_id) is True


def test_retired_rollback_flag_cannot_reactivate_legacy_execution() -> None:
    for raw in ("true", "false", "maybe"):
        policy = build_migrated_cutover_policy(
            {"ASA_EARNINGS_CALENDAR_CUTOVER_ENABLED": raw}
        )
        assert policy.is_cut_over(EARNINGS_CALENDAR_CONTRACT.strategy_id) is True


def test_migrated_strategies_are_cut_over_to_subject_first_execution() -> None:
    """Architect checkpoint: nineteenth review, "Scope it only to the
    migrated earnings_calendar strategy. FF/Skew stay on their existing
    legacy evaluation path." -- no flag exists that could register any
    other strategy_id.
    """
    policy = build_migrated_cutover_policy({})
    assert policy.is_cut_over("forward_factor") is True
    assert policy.is_cut_over("skew_momentum") is True


def test_unrelated_environment_keys_are_ignored() -> None:
    policy = build_migrated_cutover_policy(
        {"ASA_TRADIER_ENABLED": "true", "PATH": "/usr/bin"}
    )
    assert policy.is_cut_over(EARNINGS_CALENDAR_CONTRACT.strategy_id) is True
