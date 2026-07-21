"""ASA-ARCH-002 execution-domain contract tests."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain import (
    BrokerRequest,
    BrokerRequestSide,
    CanonicalInstrumentIdentity,
    Confidence,
    DomainInvariantError,
    EvidenceKind,
    EvidenceReference,
    ExecutionPlan,
    Instrument,
    InstrumentKind,
    MonetaryAmount,
    OrderType,
    PortfolioDecision,
    PortfolioDecisionState,
    ProposedPosition,
    TimeInForce,
)

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "obs-1"),)
USD = "USD"


def _proposal() -> ProposedPosition:
    instrument = Instrument(
        identity=CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"),
        kind=InstrumentKind.EQUITY,
        display_symbol="AAPL",
        currency=USD,
    )
    return ProposedPosition(
        proposed_position_id="proposal-1",
        opportunity_id="opportunity-1",
        ranking_result_id="ranking-result-1",
        ranking_id="ranking-1",
        proposal_algorithm_version="v1",
        instrument=instrument,
        target_allocation=Decimal("0.10"),
        evidence_confidence=Confidence(0.8),
        rationale=("ranked opportunity supports desired exposure",),
        effective_parameters=(
            ("maximum_allocation", Decimal("0.10")),
            ("reference_capital", Decimal("8000")),
        ),
        evidence=EVIDENCE,
    )


def _decision(
    state: PortfolioDecisionState = PortfolioDecisionState.ACCEPT,
) -> PortfolioDecision:
    proposal = _proposal()
    allocation = proposal.target_allocation
    if state in {PortfolioDecisionState.REJECT, PortfolioDecisionState.HOLD}:
        allocation = Decimal("0")
    elif state is PortfolioDecisionState.REDUCE:
        allocation = Decimal("0.05")
    return PortfolioDecision(
        portfolio_decision_id="decision-1",
        decision_algorithm_version="v1",
        portfolio_snapshot_id="snapshot-1",
        proposed_position=proposal,
        state=state,
        approved_allocation=allocation,
        policy_versions=(("buying_power", "v1"),),
        effective_parameters=(("cash_reserve", Decimal("1000")),),
        reasons=("proposal satisfies portfolio policy",),
        evidence=EVIDENCE,
    )


def _request(sequence: int = 1) -> BrokerRequest:
    decision = _decision()
    return BrokerRequest(
        broker_request_id=f"request-{sequence}",
        portfolio_decision_id=decision.portfolio_decision_id,
        sequence=sequence,
        instrument=decision.proposed_position.instrument,
        account_id="account-1",
        side=BrokerRequestSide.BUY,
        quantity=Decimal("4"),
        order_type=OrderType.LIMIT,
        limit_price=MonetaryAmount(Decimal("200"), USD),
        time_in_force=TimeInForce.DAY,
        execution_metadata=(("strategy", "single_limit_v1"),),
        reasoning=EVIDENCE,
    )


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        execution_plan_id="plan-1",
        planning_algorithm_version="v1",
        portfolio_decision=_decision(),
        broker_requests=(_request(),),
        reasoning=EVIDENCE,
    )


@pytest.mark.parametrize("value", [_decision(), _request(), _plan()])
def test_execution_contracts_are_deeply_immutable(value: object) -> None:
    assert dataclasses.is_dataclass(value)
    assert value.__dataclass_params__.frozen  # type: ignore[attr-defined]
    first_field = dataclasses.fields(value)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value, first_field, "changed")
    assert all(
        not isinstance(getattr(value, field.name), (list, dict, set))
        for field in dataclasses.fields(value)
    )


def test_identical_semantic_inputs_replay_identically() -> None:
    assert _decision() == _decision()
    assert _plan() == _plan()
    assert hash(_plan()) == hash(_plan())


def test_contract_identity_contains_no_timestamp_fields() -> None:
    for cls in (PortfolioDecision, ExecutionPlan, BrokerRequest):
        names = {field.name for field in dataclasses.fields(cls)}
        assert not names & {"created_at", "evaluated_at", "planned_at", "submitted_at"}


def test_keyed_identity_inputs_require_canonical_order() -> None:
    with pytest.raises(DomainInvariantError, match="canonical order"):
        dataclasses.replace(
            _decision(),
            effective_parameters=(
                ("maximum_position", Decimal("1000")),
                ("cash_reserve", Decimal("500")),
            ),
        )


def test_reject_and_hold_approve_no_new_exposure() -> None:
    for state in (PortfolioDecisionState.REJECT, PortfolioDecisionState.HOLD):
        decision = _decision(state)
        assert decision.approved_allocation == 0
        plan = ExecutionPlan("plan-noop", "v1", decision, (), EVIDENCE)
        assert plan.broker_requests == ()


def test_reduce_must_be_smaller_than_proposal() -> None:
    with pytest.raises(DomainInvariantError, match="smaller positive exposure"):
        dataclasses.replace(
            _decision(PortfolioDecisionState.REDUCE),
            approved_allocation=_proposal().target_allocation,
        )


def test_broker_request_is_analytical_and_contains_no_adapter_material() -> None:
    forbidden = {
        "adapter",
        "api_url",
        "credentials",
        "cookie",
        "provider_payload",
        "session",
        "token",
    }
    names = {field.name for field in dataclasses.fields(BrokerRequest)}
    assert not names & forbidden


def test_order_shape_is_structurally_coherent() -> None:
    with pytest.raises(DomainInvariantError, match="LIMIT BrokerRequest requires"):
        dataclasses.replace(_request(), limit_price=None)
    with pytest.raises(DomainInvariantError, match="MARKET BrokerRequest cannot"):
        dataclasses.replace(_request(), order_type=OrderType.MARKET)


def test_execution_plan_requires_contiguous_ordering() -> None:
    with pytest.raises(DomainInvariantError, match="sequences must be contiguous"):
        ExecutionPlan("plan-2", "v1", _decision(), (_request(sequence=2),), EVIDENCE)


def test_approved_decision_requires_analytical_request() -> None:
    with pytest.raises(DomainInvariantError, match="require at least one BrokerRequest"):
        ExecutionPlan("plan-empty", "v1", _decision(), (), EVIDENCE)
