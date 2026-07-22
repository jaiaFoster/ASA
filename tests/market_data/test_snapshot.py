from __future__ import annotations

from datetime import datetime, timezone

from domain import MarketCapability
from market_data import (
    FulfillmentStatus,
    CapabilityFulfillmentResult,
    MarketSnapshotBuilder,
    ObservationResolver,
    ProviderErrorCode,
    ResolutionPolicy,
    ResolutionResult,
    RequestBudgetManager,
    SnapshotRequest,
    SnapshotValidationMetadata,
    market_snapshot_digest,
    serialize_market_snapshot,
)
from market_data.fixture import FixtureScenario
from tests.market_data.test_fulfillment import ScriptedProvider, provider, request, service

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)
CAPABILITY = MarketCapability.REAL_TIME_QUOTE_V1


def successful_inputs() -> tuple[
    ScriptedProvider,
    CapabilityFulfillmentResult,
    ResolutionResult,
    RequestBudgetManager,
]:
    source = provider("tradier")
    fulfillment_service, budgets = service(source)
    fulfillment = fulfillment_service.fulfill(request())
    resolution = ObservationResolver().resolve(
        fulfillment.observations,
        ResolutionPolicy("v1", ("tradier",), 60, ("last",)),
        as_of=NOW,
    )
    return source, fulfillment, resolution, budgets


def test_snapshot_is_deterministic_canonical_and_self_contained() -> None:
    source, fulfillment, resolution, budgets = successful_inputs()
    builder = MarketSnapshotBuilder()
    snapshot_request = SnapshotRequest(NOW, (CAPABILITY,), (CAPABILITY,))
    arguments = (
        snapshot_request,
        (fulfillment,),
        (resolution,),
        (source.metadata,),
        (SnapshotValidationMetadata("report-1", "tradier", "passed"),),
        budgets.accounting,
    )
    first = builder.build(*arguments)
    second = builder.build(*arguments)
    assert first == second
    assert first.snapshot_digest == market_snapshot_digest(first)
    assert first.snapshot_id.endswith(first.snapshot_digest)
    assert first.completeness.missing_required_capabilities == ()
    assert first.observations == fulfillment.observations


def test_semantically_equivalent_input_order_has_same_digest() -> None:
    first_provider = provider("tradier")
    second_provider = provider("finnhub")
    fulfillment_service, budgets = service(first_provider, second_provider)
    fulfillment = fulfillment_service.fulfill(request())
    resolution = ObservationResolver().resolve(
        fulfillment.observations,
        ResolutionPolicy("v1", ("tradier", "finnhub"), 60, ("last",)),
        as_of=NOW,
    )
    builder = MarketSnapshotBuilder()
    snapshot_request = SnapshotRequest(NOW, (CAPABILITY,), ())
    first = builder.build(
        snapshot_request,
        (fulfillment,),
        (resolution,),
        (second_provider.metadata, first_provider.metadata),
        (),
        tuple(reversed(budgets.accounting)),
    )
    second = builder.build(
        snapshot_request,
        (fulfillment,),
        (resolution,),
        (first_provider.metadata, second_provider.metadata),
        (),
        budgets.accounting,
    )
    assert first.snapshot_digest == second.snapshot_digest


def test_missing_required_capability_is_explicit_without_fabricated_observation() -> None:
    failed_provider = provider(
        "tradier", FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.NO_DATA),))
    )
    fulfillment_service, budgets = service(failed_provider)
    failed = fulfillment_service.fulfill(request())
    assert failed.status is FulfillmentStatus.FAILED
    snapshot = MarketSnapshotBuilder().build(
        SnapshotRequest(NOW, (CAPABILITY,), (CAPABILITY,)),
        (failed,),
        (),
        (failed_provider.metadata,),
        (),
        budgets.accounting,
    )
    assert snapshot.observations == ()
    assert snapshot.completeness.missing_required_capabilities == (CAPABILITY,)


def test_serialized_snapshot_contains_no_secret_material() -> None:
    source, fulfillment, resolution, budgets = successful_inputs()
    snapshot = MarketSnapshotBuilder().build(
        SnapshotRequest(NOW, (CAPABILITY,), (CAPABILITY,)),
        (fulfillment,),
        (resolution,),
        (source.metadata,),
        (),
        budgets.accounting,
    )
    encoded = serialize_market_snapshot(snapshot)
    assert "password" not in encoded.lower()
    assert "authorization_header" not in encoded.lower()
    assert "test-only-placeholder" not in encoded
