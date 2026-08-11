"""SPRINT-014 S14-PR-05, Architect checkpoint: nineteenth review
("CUTOVER_PASS ... implement the already-approved PR-05 cutover
mechanism") -- build_migrated_cutover_policy()'s own environment-boundary
parsing, in isolation from refresh_with_shadow()'s own dispatch mechanics
(covered by tests/strategy_runtime/test_orchestration.py's own
TestCutoverDispatch).
"""

from __future__ import annotations

import pytest

from strategy_runtime.adapters import (
    EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR,
    build_migrated_cutover_policy,
)
from strategy_runtime.adapters.earnings_calendar import EARNINGS_CALENDAR_CONTRACT


def test_absent_flag_defaults_to_subject_first_authority() -> None:
    policy = build_migrated_cutover_policy({})
    assert policy.is_cut_over(EARNINGS_CALENDAR_CONTRACT.strategy_id) is True


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
def test_truthy_values_enable_cutover(raw: str) -> None:
    policy = build_migrated_cutover_policy({EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR: raw})
    assert policy.is_cut_over(EARNINGS_CALENDAR_CONTRACT.strategy_id) is True


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off"])
def test_falsy_values_keep_the_rollback_state(raw: str) -> None:
    policy = build_migrated_cutover_policy({EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR: raw})
    assert policy.is_cut_over(EARNINGS_CALENDAR_CONTRACT.strategy_id) is False


def test_malformed_value_raises_rather_than_silently_defaulting() -> None:
    with pytest.raises(ValueError, match=EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR):
        build_migrated_cutover_policy({EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR: "maybe"})


def test_migrated_strategies_are_cut_over_to_subject_first_execution() -> None:
    """Architect checkpoint: nineteenth review, "Scope it only to the
    migrated earnings_calendar strategy. FF/Skew stay on their existing
    legacy evaluation path." -- no flag exists that could register any
    other strategy_id.
    """
    policy = build_migrated_cutover_policy({EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR: "true"})
    assert policy.is_cut_over("forward_factor") is True
    assert policy.is_cut_over("skew_momentum") is True


def test_unrelated_environment_keys_are_ignored() -> None:
    policy = build_migrated_cutover_policy(
        {"ASA_TRADIER_ENABLED": "true", "PATH": "/usr/bin"}
    )
    assert policy.is_cut_over(EARNINGS_CALENDAR_CONTRACT.strategy_id) is True
