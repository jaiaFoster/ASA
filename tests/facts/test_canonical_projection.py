"""SPRINT-014 S14-PR-04: canonical fact projection tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from domain.canonical_fact import CanonicalFact
from facts.canonical_projection import project_canonical_fact
from market_data.resolution import ObservationResolver, ResolutionPolicy
from tests.market_data.test_fulfillment import provider, request, service

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)


def _resolved_result():
    source = provider("tradier")
    fulfillment, _ = service(source)
    result = fulfillment.fulfill(request())
    resolution = ObservationResolver().resolve(
        result.observations,
        ResolutionPolicy("v1", ("tradier",), 60, ("last",)),
        as_of=NOW,
    )
    return resolution


def test_projects_a_canonical_fact_from_a_resolved_result() -> None:
    resolution = _resolved_result()
    fact = project_canonical_fact(
        resolution,
        value=Decimal("189.50"),
        fact_id="spot_price:AAPL:cycle-1",
        version=1,
        fact_type="spot_price",
        created_time=NOW,
    )
    assert isinstance(fact, CanonicalFact)
    assert fact.value == Decimal("189.50")
    assert fact.fact_type == "spot_price"
    assert fact.provenance.contributing_observation_ids == resolution.consumed_observation_ids
    selected = resolution.selected_observation
    assert selected is not None
    assert fact.provenance.selected_provider_id == selected.provenance.provider_id


def test_unresolved_resolution_projects_to_none_not_a_fabricated_fact() -> None:
    source = provider("tradier")
    fulfillment, _ = service(source)
    result = fulfillment.fulfill(request())
    # A policy whose freshness threshold nothing can satisfy forces
    # ResolutionMethod.UNRESOLVED without needing a second, failing fixture.
    unresolved = ObservationResolver().resolve(
        result.observations,
        ResolutionPolicy("v1", ("tradier",), 0, ("last",)),
        as_of=NOW + timedelta(seconds=1),
    )
    fact = project_canonical_fact(
        unresolved,
        value=Decimal("1"),
        fact_id="spot_price:AAPL:cycle-1",
        version=1,
        fact_type="spot_price",
        created_time=NOW,
    )
    assert fact is None


def test_fact_identity_reflects_the_supplied_fact_id_and_version() -> None:
    resolution = _resolved_result()
    fact = project_canonical_fact(
        resolution,
        value=Decimal("1"),
        fact_id="spot_price:AAPL:cycle-1",
        version=3,
        fact_type="spot_price",
        created_time=NOW,
    )
    assert fact is not None
    assert fact.fact_id == "spot_price:AAPL:cycle-1"
    assert fact.version == 3


def test_field_disagreements_are_recorded_in_reconciliation_metadata() -> None:
    resolution = _resolved_result()
    fact = project_canonical_fact(
        resolution,
        value=Decimal("1"),
        fact_id="spot_price:AAPL:cycle-1",
        version=1,
        fact_type="spot_price",
        created_time=NOW,
    )
    assert fact is not None
    keys = {key for key, _ in fact.provenance.reconciliation_metadata}
    assert "resolution_method" in keys
    assert "field_disagreement_count" in keys
