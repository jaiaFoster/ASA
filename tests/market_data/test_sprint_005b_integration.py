from __future__ import annotations

from datetime import datetime, timezone

from domain import MarketCapability
from market_data import (
    BudgetScope,
    CapabilityFulfillmentService,
    CapabilityRegistry,
    MarketSnapshotBuilder,
    ObservationResolver,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
    RequestBudgetManager,
    RequestBudgetPolicy,
    ResolutionPolicy,
    SnapshotReplayRecord,
    SnapshotRequest,
    replay_market_snapshot,
)
from tests.market_data.test_budget import FakeClock
from tests.market_data.test_fixture_provider import provider, request

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)


def test_complete_fixture_capability_snapshot_and_replay_path() -> None:
    source = provider()
    registry = ProviderRegistry((source,))
    capabilities = source.capabilities
    capability_registry = CapabilityRegistry(
        registry,
        ProviderPriorityPolicy(
            "sprint-005b-v1",
            tuple(
                ProviderPriority(capability, (source.provider_id,)) for capability in capabilities
            ),
        ),
    )
    budget = RequestBudgetManager(
        (
            RequestBudgetPolicy(
                source.provider_id,
                BudgetScope.RUNTIME,
                len(capabilities),
                len(capabilities),
                0,
                "v1",
            ),
        ),
        FakeClock(NOW),
    )
    fulfillment = CapabilityFulfillmentService(registry, capability_registry, budget)
    fields = {
        MarketCapability.REAL_TIME_QUOTE_V1: ("last",),
        MarketCapability.HISTORICAL_BARS_V1: ("open", "close"),
        MarketCapability.OPTION_CHAIN_V1: (
            "contracts",
            "greeks",
            "implied_volatility",
            "volume",
            "open_interest",
        ),
        MarketCapability.EARNINGS_CALENDAR_V1: ("earnings_date",),
    }
    fulfillments = tuple(
        fulfillment.fulfill(request(capability, fields[capability])) for capability in capabilities
    )
    resolutions = tuple(
        ObservationResolver().resolve(
            result.observations,
            ResolutionPolicy(
                "sprint-005b-v1",
                (source.provider_id,),
                60,
                fields[result.request.capability],
            ),
            as_of=NOW,
        )
        for result in fulfillments
    )
    snapshot = MarketSnapshotBuilder().build(
        SnapshotRequest(NOW, capabilities, capabilities),
        fulfillments,
        resolutions,
        (source.metadata,),
        (),
        budget.accounting,
    )
    replay = replay_market_snapshot(SnapshotReplayRecord(snapshot, snapshot.snapshot_digest))

    assert set(snapshot.completeness.resolved_capabilities) == set(capabilities)
    assert snapshot.completeness.missing_required_capabilities == ()
    assert len(snapshot.observations) == len(capabilities)
    assert replay.observations == snapshot.observations
    assert replay.snapshot_digest == snapshot.snapshot_digest
    assert len(budget.accounting) == len(capabilities)
