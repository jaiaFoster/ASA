"""PT-05: shared expiration mechanics never leak another strategy's reason."""

from datetime import UTC, date, datetime

from domain import (
    EvidenceKind,
    EvidenceReference,
    EvidenceUsability,
    ExpirationCollection,
    ExpirationCycle,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from strategies import bxm_planning, cboe_put_planning


def test_missing_expirations_have_consumer_owned_reasons() -> None:
    now = datetime(2026, 10, 16, 15, tzinfo=UTC)
    put = cboe_put_planning.expand_demands({}, now=now)
    bxm = bxm_planning.expand_demands({}, now=now)
    assert put.unknown_reasons == (UnknownReason("G_PUT_STRIKE_EXISTS_UNKNOWN"),)
    assert bxm.unknown_reasons == (UnknownReason("G_BXM_STRIKE_EXISTS_UNKNOWN"),)
    assert put.demands == bxm.demands == ()


def test_empty_monthly_inventory_retains_put_reason() -> None:
    assert cboe_put_planning._next_month_expiration((), date(2026, 12, 18)) == UnknownReason(
        "G_PUT_STRIKE_EXISTS_UNKNOWN"
    )


def test_shared_monthly_selection_preserves_exact_demand_identity() -> None:
    now = datetime(2026, 12, 18, 15, tzinfo=UTC)
    evidence = (EvidenceReference(EvidenceKind.OBSERVATION, "expirations", 1),)
    weekly = ExpirationCycle(date(2027, 1, 8), 21, False, True, now.date(), evidence)
    monthly = ExpirationCycle(date(2027, 1, 15), 28, True, False, now.date(), evidence)
    demand = cboe_put_planning.expirations_demand(now)
    resolved = ResolvedCapabilityEvidence(
        demand.demand_id,
        demand.capability,
        EvidenceUsability.RESOLVED,
        ExpirationCollection(now.date(), (monthly, weekly)),
        ("expirations",),
        None,
    )
    inputs = {demand.demand_id: resolved}
    put = cboe_put_planning.expand_demands(inputs, now=now)
    bxm = bxm_planning.expand_demands(inputs, now=now)
    assert put == bxm
    assert put.demands == (cboe_put_planning.chain_demand(now, monthly.expiration_date),)
    assert put.selections == (("expiration", "2027-01-15"),)


def test_resolved_but_absent_monthly_inventory_uses_consumer_reason() -> None:
    now = datetime(2026, 12, 18, 15, tzinfo=UTC)
    demand = cboe_put_planning.expirations_demand(now)
    resolved = ResolvedCapabilityEvidence(
        demand.demand_id,
        demand.capability,
        EvidenceUsability.RESOLVED,
        ExpirationCollection(now.date(), ()),
        ("expirations",),
        None,
    )
    inputs = {demand.demand_id: resolved}
    assert bxm_planning.expand_demands(inputs, now=now).unknown_reasons == (
        UnknownReason("G_BXM_STRIKE_EXISTS_UNKNOWN"),
    )
    assert cboe_put_planning.expand_demands(inputs, now=now).unknown_reasons == (
        UnknownReason("G_PUT_STRIKE_EXISTS_UNKNOWN"),
    )
