from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.values import DomainInvariantError
from screening.cycle_identity import new_screening_cycle_id, pair_evaluation_id

NOW = datetime(2026, 7, 21, 16, 0, 0, 123456, tzinfo=UTC)


def test_new_screening_cycle_id_is_deterministic_from_timestamp() -> None:
    first = new_screening_cycle_id(NOW)
    second = new_screening_cycle_id(NOW)
    assert first == second
    assert first.startswith("cycle_")


def test_new_screening_cycle_id_differs_by_timestamp() -> None:
    other = datetime(2026, 7, 21, 16, 0, 1, 123456, tzinfo=UTC)
    assert new_screening_cycle_id(NOW) != new_screening_cycle_id(other)


def test_new_screening_cycle_id_requires_tz_aware() -> None:
    with pytest.raises(DomainInvariantError):
        new_screening_cycle_id(datetime(2026, 7, 21, 16, 0))


def test_pair_evaluation_id_is_deterministic() -> None:
    cycle = new_screening_cycle_id(NOW)
    first = pair_evaluation_id(cycle, "forward_factor", "AAPL")
    second = pair_evaluation_id(cycle, "forward_factor", "AAPL")
    assert first == second


def test_pair_evaluation_id_differs_by_signal_and_symbol() -> None:
    cycle = new_screening_cycle_id(NOW)
    assert pair_evaluation_id(cycle, "forward_factor", "AAPL") != pair_evaluation_id(
        cycle, "skew_momentum", "AAPL"
    )
    assert pair_evaluation_id(cycle, "forward_factor", "AAPL") != pair_evaluation_id(
        cycle, "forward_factor", "MSFT"
    )


@pytest.mark.parametrize(
    "cycle,signal_id,symbol",
    [("", "forward_factor", "AAPL"), ("cycle_1", "", "AAPL"), ("cycle_1", "forward_factor", "")],
)
def test_pair_evaluation_id_rejects_empty_components(cycle, signal_id, symbol) -> None:
    with pytest.raises(ValueError):
        pair_evaluation_id(cycle, signal_id, symbol)
