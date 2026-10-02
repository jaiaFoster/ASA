"""Generic INDEX_SETTLEMENT_VALUE_V1 reducer over the real BXM and SCS demands."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from market_data.capability_coalescing import reduce_index_settlement_results
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    FulfillmentStatus,
    ProviderFulfillmentAttempt,
)
from market_data.providers import CapabilityRequest, ProviderStatus
from screening.subject_planning import _to_capability_request
from strategies.bxm_planning import settlement_value_demand
from strategies.scs_planning import expirations_demand, settlement_demand

NOW = datetime(2026, 10, 2, 16, tzinfo=UTC)
BXM = _to_capability_request("SPX", settlement_value_demand(NOW), now=NOW)  # 35-day lookback
SCS = _to_capability_request("SPX", settlement_demand(NOW), now=NOW)  # 7-day lookback
# Sentinel observations: the reducer must copy them unchanged, never inspect or invent.
BXM_OBS, SCS_OBS = object(), object()


def _ok(
    request: CapabilityRequest, observation: object, provider: str
) -> CapabilityFulfillmentResult:
    attempt = ProviderFulfillmentAttempt(
        provider, 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    return CapabilityFulfillmentResult(
        request,
        FulfillmentStatus.FULFILLED,
        provider,
        (observation,),
        (attempt,),
        False,  # type: ignore[arg-type]
    )


def _failed(request: CapabilityRequest) -> CapabilityFulfillmentResult:
    attempt = ProviderFulfillmentAttempt("p", 1, ProviderStatus.UNAVAILABLE, (), "down", ())
    return CapabilityFulfillmentResult(
        request, FulfillmentStatus.FAILED, None, (), (attempt,), False
    )


def test_rejects_other_capabilities_and_empty_input() -> None:
    chain = _to_capability_request("SPX", expirations_demand(NOW), now=NOW)
    with pytest.raises(ValueError):
        reduce_index_settlement_results((_failed(chain),))
    with pytest.raises(ValueError):
        reduce_index_settlement_results(())


def test_both_succeed_selects_earliest_start_deterministically() -> None:
    for ordering in (
        (_ok(BXM, BXM_OBS, "pb"), _ok(SCS, SCS_OBS, "ps")),
        (_ok(SCS, SCS_OBS, "ps"), _ok(BXM, BXM_OBS, "pb")),
    ):
        sealed = reduce_index_settlement_results(ordering)
        assert sealed.status is FulfillmentStatus.FULFILLED
        assert sealed.request is BXM and sealed.selected_provider == "pb"
        assert sealed.observations == (BXM_OBS,)
        assert len(sealed.attempts) == 2


def test_partial_success_is_degraded_and_keeps_the_successful_result() -> None:
    sealed = reduce_index_settlement_results((_failed(BXM), _ok(SCS, SCS_OBS, "ps")))
    assert sealed.status is FulfillmentStatus.DEGRADED
    assert sealed.request is SCS and sealed.observations == (SCS_OBS,)
    assert len(sealed.attempts) == 2
    sealed = reduce_index_settlement_results((_ok(BXM, BXM_OBS, "pb"), _failed(SCS)))
    assert sealed.status is FulfillmentStatus.DEGRADED and sealed.request is BXM


def test_all_failed_seals_one_typed_failure_with_every_attempt() -> None:
    sealed = reduce_index_settlement_results((_failed(SCS), _failed(BXM)))
    assert sealed.status is FulfillmentStatus.FAILED
    assert sealed.selected_provider is None and sealed.observations == ()
    assert sealed.request is BXM and len(sealed.attempts) == 2
