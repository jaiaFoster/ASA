"""Pure deterministic evaluation of declared RiskPolicy values."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

from domain.canonicalization import serialize_canonical
from domain.execution import (
    PolicyOutcome,
    PortfolioDelta,
    PortfolioDeltaKind,
    PortfolioEvaluationDisposition,
    PortfolioEvaluationResult,
    RiskDecision,
    RiskDecisionState,
)
from domain.operational import PortfolioSnapshot, RiskPolicy, RiskPolicyScope, RiskPolicyType
from domain.references import EvidenceReference
from risk.errors import InvalidRiskInputError
from risk.models import POLICY_OUTCOME_NAMESPACE, RISK_ALGORITHM_VERSION, RISK_DECISION_NAMESPACE


def _key(item: EvidenceReference) -> tuple[object, ...]:
    return item.kind.value, item.referenced_id, item.version


def _id(namespace: str, *values: object) -> str:
    payload = "\n".join((namespace, *(serialize_canonical(value) for value in values)))
    return hashlib.sha256(payload.encode()).hexdigest()


def _parameter(policy: RiskPolicy, name: str) -> Decimal | bool:
    values = dict(policy.parameters)
    if name not in values:
        raise InvalidRiskInputError(f"{policy.policy_type.value} requires {name}")
    return values[name]


def _valuation(snapshot: PortfolioSnapshot, delta: PortfolioDelta):  # type: ignore[no-untyped-def]
    matches = tuple(
        item for item in snapshot.instrument_valuations
        if item.instrument.identity == delta.instrument.identity
    )
    if len(matches) != 1:
        raise InvalidRiskInputError("Risk requires one matching valuation")
    return matches[0]


def _observed(policy: RiskPolicy, delta: PortfolioDelta, snapshot: PortfolioSnapshot) -> tuple[str, str, bool]:
    portfolio = snapshot.portfolio
    valuation = _valuation(snapshot, delta)
    target_exposure = delta.target_quantity * valuation.unit_exposure.amount
    nlv = portfolio.net_liquidation_value.amount
    if policy.policy_type is RiskPolicyType.BUYING_POWER:
        threshold = Decimal(_parameter(policy, "minimum_remaining_amount"))
        observed = portfolio.buying_power.amount + delta.buying_power_change.amount
        return str(threshold), str(observed), observed >= threshold
    if policy.policy_type is RiskPolicyType.CASH_RESERVE:
        threshold = Decimal(_parameter(policy, "minimum_cash_ratio"))
        if nlv <= 0:
            raise InvalidRiskInputError("ratio policies require positive net liquidation value")
        observed = (portfolio.cash_balance.amount + delta.cash_change.amount) / nlv
        return str(threshold), str(observed), observed >= threshold
    if policy.policy_type is RiskPolicyType.MAX_POSITION_ALLOCATION:
        threshold = Decimal(_parameter(policy, "maximum_ratio"))
        if nlv <= 0:
            raise InvalidRiskInputError("ratio policies require positive net liquidation value")
        observed = target_exposure / nlv
        return str(threshold), str(observed), observed <= threshold
    if policy.policy_type is RiskPolicyType.MAX_SINGLE_ASSET_EXPOSURE:
        threshold = Decimal(_parameter(policy, "maximum_ratio"))
        observed = target_exposure / nlv
        return str(threshold), str(observed), observed <= threshold
    if policy.policy_type is RiskPolicyType.MAX_SECTOR_EXPOSURE:
        threshold = Decimal(_parameter(policy, "maximum_ratio"))
        if delta.instrument.sector is None:
            raise InvalidRiskInputError("sector policy requires sector classification")
        other = sum((
            item.gross_exposure.amount for item in portfolio.positions
            if item.instrument.sector == delta.instrument.sector
            and item.instrument.identity != delta.instrument.identity
        ), Decimal("0"))
        observed = (other + target_exposure) / nlv
        return str(threshold), str(observed), observed <= threshold
    if policy.policy_type is RiskPolicyType.DUPLICATE_EXPOSURE:
        allowed = bool(_parameter(policy, "allow_increase_existing"))
        duplicate_increase = delta.starting_quantity > 0 and delta.target_quantity > delta.starting_quantity
        return str(allowed), str(duplicate_increase), allowed or not duplicate_increase
    threshold = Decimal(_parameter(policy, "maximum_amount"))
    observed = delta.projected_maximum_loss.amount
    return str(threshold), str(observed), observed <= threshold


def _outcome(policy: RiskPolicy, delta: PortfolioDelta, snapshot: PortfolioSnapshot) -> PolicyOutcome:
    threshold, observed, passed = _observed(policy, delta, snapshot)
    inputs = (("portfolio_delta_id", delta.portfolio_delta_id), ("source_snapshot_id", snapshot.portfolio_snapshot_id))
    evidence = policy.evidence + delta.evidence
    values = (policy.risk_policy_id, policy.policy_version, inputs, threshold, observed, passed, tuple(_key(item) for item in evidence))
    return PolicyOutcome(
        _id(POLICY_OUTCOME_NAMESPACE, values), policy.risk_policy_id, policy.policy_version,
        inputs, "policy_comparison", threshold, observed, passed,
        (("policy passed" if passed else "policy failed"),), evidence,
    )


def _approved(delta: PortfolioDelta) -> PortfolioDelta:
    values = (delta.portfolio_delta_id, PortfolioDeltaKind.APPROVED.value)
    return replace(
        delta,
        portfolio_delta_id=_id("asa.portfolio_delta.v1", values),
        kind=PortfolioDeltaKind.APPROVED,
        predecessor_delta_id=delta.portfolio_delta_id,
    )


def evaluate_risk(
    result: PortfolioEvaluationResult,
    snapshot: PortfolioSnapshot,
    strategy_policies: tuple[RiskPolicy, ...] = (),
    reduced_candidates: tuple[PortfolioDelta, ...] = (),
) -> RiskDecision:
    if result.disposition is not PortfolioEvaluationDisposition.DELTA_PRODUCED or result.proposed_delta is None:
        raise InvalidRiskInputError("Risk accepts only DELTA_PRODUCED results")
    proposed = result.proposed_delta
    policies = tuple(sorted(
        (*snapshot.portfolio.platform_risk_policies, *strategy_policies),
        key=lambda item: (0 if item.scope is RiskPolicyScope.PLATFORM else 1, item.policy_type.value, item.risk_policy_id),
    ))
    candidates = (proposed, *reduced_candidates)
    selected: PortfolioDelta | None = None
    selected_outcomes: tuple[PolicyOutcome, ...] = ()
    for candidate in candidates:
        outcomes = tuple(_outcome(policy, candidate, snapshot) for policy in policies)
        if all(outcome.passed for outcome in outcomes):
            selected, selected_outcomes = candidate, outcomes
            break
        if not selected_outcomes:
            selected_outcomes = outcomes
    state = RiskDecisionState.REJECT
    approved = None
    if selected is proposed:
        state, approved = RiskDecisionState.APPROVE, _approved(proposed)
    elif selected is not None:
        state, approved = RiskDecisionState.REDUCE, _approved(selected)
    reasons = tuple(reason for outcome in selected_outcomes for reason in outcome.reasons)
    evidence = result.evidence + tuple(item for policy in policies for item in policy.evidence)
    values = (result.portfolio_evaluation_result_id, state.value, approved.portfolio_delta_id if approved else None, tuple(item.policy_outcome_id for item in selected_outcomes))
    return RiskDecision(
        _id(RISK_DECISION_NAMESPACE, values), RISK_ALGORITHM_VERSION,
        snapshot.portfolio_snapshot_id, proposed, state, approved, selected_outcomes,
        tuple(policy.risk_policy_id for policy in policies),
        tuple((policy.risk_policy_id, str(policy.parameters)) for policy in policies),
        reasons or ("risk rejected",), evidence,
    )
