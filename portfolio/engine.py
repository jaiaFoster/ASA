"""Pure deterministic Portfolio Engine (ASA-CORE-009)."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from domain.canonicalization import serialize_canonical
from domain.execution import PortfolioDecision, PortfolioDecisionState
from domain.operational import PortfolioDecisionRequest, PortfolioSnapshot, ProposedPosition
from domain.references import EvidenceReference
from portfolio.models import (
    ALLOCATION_QUANTUM,
    PORTFOLIO_ALGORITHM_VERSION,
    PORTFOLIO_IDENTITY_NAMESPACE,
    PolicyOutcome,
    PortfolioParameters,
)
from portfolio.errors import InvalidPolicyOutcomeError
from portfolio.registry import PolicyRegistry, build_default_registry


def _evidence_identity(reference: EvidenceReference) -> tuple[object, ...]:
    return (reference.kind.value, reference.referenced_id, reference.version)


def _decision_evidence(
    proposal: ProposedPosition, snapshot: PortfolioSnapshot
) -> tuple[EvidenceReference, ...]:
    references = proposal.evidence + snapshot.evidence + tuple(
        reference
        for holding in snapshot.holdings
        for reference in holding.valuation_evidence
    )
    unique = {
        _evidence_identity(reference): reference
        for reference in references
    }
    return tuple(unique[key] for key in sorted(unique))


def _identity(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    state: PortfolioDecisionState,
    approved_allocation: Decimal,
    policy_versions: tuple[tuple[str, str], ...],
    effective_parameters: tuple[tuple[str, Decimal], ...],
    reasons: tuple[str, ...],
    evidence: tuple[EvidenceReference, ...],
) -> str:
    payload = "\n".join(
        (
            PORTFOLIO_IDENTITY_NAMESPACE,
            PORTFOLIO_ALGORITHM_VERSION,
            serialize_canonical(proposal.proposed_position_id),
            serialize_canonical(snapshot.portfolio_snapshot_id),
            serialize_canonical(state.value),
            serialize_canonical(approved_allocation),
            serialize_canonical(policy_versions),
            serialize_canonical(effective_parameters),
            serialize_canonical(reasons),
            serialize_canonical(tuple(_evidence_identity(item) for item in evidence)),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _disposition(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    outcomes: tuple[PolicyOutcome, ...],
) -> tuple[PortfolioDecisionState, Decimal, tuple[str, ...]]:
    reasons = tuple(outcome.reason for outcome in outcomes)
    if proposal.instrument.currency != snapshot.base_currency:
        return (
            PortfolioDecisionState.REJECT,
            Decimal("0"),
            (*reasons, "instrument currency does not match portfolio base currency"),
        )
    terminal = next(
        (outcome.terminal_state for outcome in outcomes if outcome.terminal_state is not None),
        None,
    )
    if terminal is not None:
        return terminal, Decimal("0"), reasons
    approved = min(
        (proposal.target_allocation, *(outcome.maximum_allocation for outcome in outcomes))
    )
    approved = max(Decimal("0"), approved).quantize(ALLOCATION_QUANTUM)
    if approved == 0:
        return PortfolioDecisionState.REJECT, approved, reasons
    if approved < proposal.target_allocation:
        return PortfolioDecisionState.REDUCE, approved, reasons
    return PortfolioDecisionState.ACCEPT, proposal.target_allocation, reasons


def _evaluate_one(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters,
    registry: PolicyRegistry,
) -> PortfolioDecision:
    definitions = registry.definitions()
    outcomes = tuple(
        definition.policy(proposal, snapshot, parameters) for definition in definitions
    )
    if any(
        outcome.policy_name != definition.name
        for definition, outcome in zip(definitions, outcomes, strict=True)
    ):
        raise InvalidPolicyOutcomeError("policy outcome name does not match registry definition")
    state, approved, reasons = _disposition(proposal, snapshot, outcomes)
    policy_versions = tuple(
        (outcome.policy_name, outcome.policy_version) for outcome in outcomes
    )
    effective_parameters = parameters.canonical_items()
    evidence = _decision_evidence(proposal, snapshot)
    return PortfolioDecision(
        portfolio_decision_id=_identity(
            proposal,
            snapshot,
            state,
            approved,
            policy_versions,
            effective_parameters,
            reasons,
            evidence,
        ),
        decision_algorithm_version=PORTFOLIO_ALGORITHM_VERSION,
        portfolio_snapshot_id=snapshot.portfolio_snapshot_id,
        proposed_position=proposal,
        state=state,
        approved_allocation=approved,
        policy_versions=policy_versions,
        effective_parameters=effective_parameters,
        reasons=reasons,
        evidence=evidence,
    )


def evaluate_portfolio(
    request: PortfolioDecisionRequest,
    parameters: PortfolioParameters | None = None,
    registry: PolicyRegistry | None = None,
) -> tuple[PortfolioDecision, ...]:
    """Evaluate proposals in ranking order against one immutable snapshot."""
    active_parameters = parameters or PortfolioParameters()
    active_registry = registry or build_default_registry()
    active_registry.validate()
    return tuple(
        _evaluate_one(proposal, request.portfolio_snapshot, active_parameters, active_registry)
        for proposal in request.proposed_positions
    )
