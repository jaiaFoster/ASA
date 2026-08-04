from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from screening.cycle_identity import (
    manual_invocation_slot_id,
    new_screening_cycle_id,
    pair_evaluation_id,
    scope_identity,
)

UNIVERSE = (("forward_factor", "AAPL"), ("skew_momentum", "AAPL"), ("earnings_calendar", "MSFT"))


# -- scope_identity -----------------------------------------------------


def test_scope_identity_is_order_independent() -> None:
    reversed_universe = tuple(reversed(UNIVERSE))
    assert scope_identity(UNIVERSE) == scope_identity(reversed_universe)


def test_scope_identity_differs_for_different_universes() -> None:
    smaller = UNIVERSE[:-1]
    assert scope_identity(UNIVERSE) != scope_identity(smaller)


def test_scope_identity_rejects_empty_universe() -> None:
    with pytest.raises(ValueError):
        scope_identity(())


# -- manual_invocation_slot_id (timezone normalization) ------------------


def test_manual_invocation_slot_id_normalizes_timezone_representation() -> None:
    utc_instant = datetime(2026, 7, 21, 20, 0, tzinfo=UTC)
    same_instant_other_tz = utc_instant.astimezone(timezone(timedelta(hours=-4)))
    # Same absolute instant, different tzinfo representation -- the raw
    # isoformat() strings differ even though the instants are equal, which
    # is exactly what would leak into the hash without astimezone(UTC)
    # normalization first.
    assert utc_instant.isoformat() != same_instant_other_tz.isoformat()
    assert manual_invocation_slot_id(utc_instant) == manual_invocation_slot_id(
        same_instant_other_tz
    )


def test_manual_invocation_slot_id_differs_for_different_instants() -> None:
    first = datetime(2026, 7, 21, 20, 0, tzinfo=UTC)
    second = datetime(2026, 7, 21, 20, 0, 1, tzinfo=UTC)
    assert manual_invocation_slot_id(first) != manual_invocation_slot_id(second)


def test_manual_invocation_slot_id_requires_tz_aware() -> None:
    with pytest.raises(ValueError):
        manual_invocation_slot_id(datetime(2026, 7, 21, 20, 0))


# -- new_screening_cycle_id -----------------------------------------------


def test_new_screening_cycle_id_is_deterministic_for_the_same_tuple() -> None:
    scope = scope_identity(UNIVERSE)
    first = new_screening_cycle_id(invocation_type="scheduled", slot_id="slot_abc", scope_id=scope)
    second = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_abc", scope_id=scope
    )
    assert first == second
    assert first.startswith("cycle_")


def test_repeated_slot_reprocessing_is_idempotent_at_the_cycle_level() -> None:
    """A retried scheduled slot (same slot_id, e.g. after a claim-repository
    retry) must resolve to the same cycle_id as the original attempt."""
    scope = scope_identity(UNIVERSE)
    original = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_2026-07-21-3", scope_id=scope
    )
    retried = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_2026-07-21-3", scope_id=scope
    )
    assert original == retried


def test_overlapping_invocation_types_never_collide() -> None:
    """A scheduled run and a concurrent manual run over the same slot/scope
    must never resolve to the same cycle_id."""
    scope = scope_identity(UNIVERSE)
    scheduled = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_shared", scope_id=scope
    )
    manual = new_screening_cycle_id(invocation_type="manual", slot_id="slot_shared", scope_id=scope)
    assert scheduled != manual


def test_new_screening_cycle_id_collision_across_distinguishing_components() -> None:
    scope_a = scope_identity(UNIVERSE)
    scope_b = scope_identity(UNIVERSE[:-1])
    base = new_screening_cycle_id(invocation_type="scheduled", slot_id="slot_1", scope_id=scope_a)
    different_slot = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_2", scope_id=scope_a
    )
    different_scope = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_1", scope_id=scope_b
    )
    different_type = new_screening_cycle_id(
        invocation_type="manual", slot_id="slot_1", scope_id=scope_a
    )
    assert len({base, different_slot, different_scope, different_type}) == 4


@pytest.mark.parametrize(
    "invocation_type,slot_id,scope_id",
    [("", "slot_1", "scope_1"), ("scheduled", "", "scope_1"), ("scheduled", "slot_1", "")],
)
def test_new_screening_cycle_id_rejects_empty_components(
    invocation_type, slot_id, scope_id
) -> None:
    with pytest.raises(ValueError):
        new_screening_cycle_id(
            invocation_type=invocation_type, slot_id=slot_id, scope_id=scope_id
        )


def test_new_screening_cycle_id_rejects_colon_in_components() -> None:
    with pytest.raises(ValueError):
        new_screening_cycle_id(invocation_type="sched:uled", slot_id="slot_1", scope_id="scope_1")


# -- pair_evaluation_id -----------------------------------------------


def test_pair_evaluation_id_is_deterministic() -> None:
    cycle = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_1", scope_id=scope_identity(UNIVERSE)
    )
    first = pair_evaluation_id(cycle, "forward_factor", "AAPL")
    second = pair_evaluation_id(cycle, "forward_factor", "AAPL")
    assert first == second


def test_pair_evaluation_id_differs_by_strategy_and_subject() -> None:
    cycle = new_screening_cycle_id(
        invocation_type="scheduled", slot_id="slot_1", scope_id=scope_identity(UNIVERSE)
    )
    assert pair_evaluation_id(cycle, "forward_factor", "AAPL") != pair_evaluation_id(
        cycle, "skew_momentum", "AAPL"
    )
    assert pair_evaluation_id(cycle, "forward_factor", "AAPL") != pair_evaluation_id(
        cycle, "forward_factor", "MSFT"
    )


@pytest.mark.parametrize(
    "cycle,strategy_id,subject",
    [("", "forward_factor", "AAPL"), ("cycle_1", "", "AAPL"), ("cycle_1", "forward_factor", "")],
)
def test_pair_evaluation_id_rejects_empty_components(cycle, strategy_id, subject) -> None:
    with pytest.raises(ValueError):
        pair_evaluation_id(cycle, strategy_id, subject)


def test_pair_evaluation_id_rejects_colon_in_components() -> None:
    with pytest.raises(ValueError):
        pair_evaluation_id("cycle_1", "forward:factor", "AAPL")
