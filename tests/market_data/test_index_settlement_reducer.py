"""Generic INDEX_SETTLEMENT_VALUE_V1 reducer for distinct consumer lookbacks."""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta

import pytest

from domain import MarketCapability
from market_data.capability_coalescing import reduce_index_settlement_results
from market_data.fulfillment import CapabilityFulfillmentResult, FulfillmentStatus

NOW = datetime(2026, 10, 2, 16, tzinfo=UTC)


def _result(days: int, *, observations: tuple[object, ...] = ()) -> CapabilityFulfillmentResult:
    from unittest.mock import MagicMock

    request = MagicMock()
    request.capability = MarketCapability.INDEX_SETTLEMENT_VALUE_V1
    request.effective_start = NOW - timedelta(days=days)
    request.effective_end = NOW
    request.subjects = ()
    attempt = MagicMock(name=f"attempt-{days}")
    result = MagicMock(spec=CapabilityFulfillmentResult)
    result.request = request
    result.observations = observations
    result.attempts = (attempt,)
    result.status = FulfillmentStatus.FULFILLED if observations else FulfillmentStatus.FAILED
    return result


def test_reducer_rejects_other_capabilities() -> None:
    other = _result(7)
    other.request.capability = MarketCapability.OPTION_CHAIN_V1
    with pytest.raises(ValueError):
        reduce_index_settlement_results((other,))
    with pytest.raises(ValueError):
        reduce_index_settlement_results(())


def test_failed_lookbacks_seal_as_one_failure_with_every_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dataclasses, "replace", lambda item, **changes: (item, changes))
    seven, thirty_five = _result(7), _result(35)
    sealed, changes = reduce_index_settlement_results((seven, thirty_five))
    assert sealed is thirty_five  # widest window is the representative
    assert changes["attempts"] == seven.attempts + thirty_five.attempts


def test_widest_successful_lookback_is_the_deterministic_representative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dataclasses, "replace", lambda item, **changes: (item, changes))
    seven = _result(7, observations=("soq-2026-09-30",))
    thirty_five = _result(35, observations=("soq-2026-09-18",))
    for ordering in ((seven, thirty_five), (thirty_five, seven)):
        sealed, changes = reduce_index_settlement_results(ordering)
        assert sealed is thirty_five
        assert changes["status"] is FulfillmentStatus.FULFILLED
    sealed, changes = reduce_index_settlement_results((seven, _result(35)))
    assert sealed is seven
    assert changes["status"] is FulfillmentStatus.DEGRADED
    assert date(2026, 10, 2)  # anchor date for the fixture windows
