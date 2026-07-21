"""Pure Portfolio Engine calculation owner (ASA-ARCH-006)."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN, localcontext

from domain.canonicalization import serialize_canonical
from domain.execution import (
    PortfolioDelta,
    PortfolioDeltaKind,
    PortfolioEvaluationDisposition,
    PortfolioEvaluationResult,
)
from domain.operational import (
    InstrumentValuation,
    MonetaryAmount,
    PortfolioEvaluationRequest,
    PortfolioSnapshot,
    Position,
    PositionDirection,
    ProposedPosition,
)
from domain.references import EvidenceReference
from domain.values import DomainInvariantError
from portfolio.models import (
    PORTFOLIO_ALGORITHM_VERSION,
    PORTFOLIO_DELTA_NAMESPACE,
    PORTFOLIO_EVALUATION_NAMESPACE,
    PortfolioParameters,
)


def _evidence_key(item: EvidenceReference) -> tuple[object, ...]:
    return item.kind.value, item.referenced_id, item.version


def _evidence(*groups: tuple[EvidenceReference, ...]) -> tuple[EvidenceReference, ...]:
    unique = {_evidence_key(item): item for group in groups for item in group}
    return tuple(unique[key] for key in sorted(unique))


def _identity(namespace: str, *values: object) -> str:
    payload = "\n".join((namespace, *(serialize_canonical(value) for value in values)))
    return hashlib.sha256(payload.encode()).hexdigest()


def _valuation(proposal: ProposedPosition, snapshot: PortfolioSnapshot) -> InstrumentValuation:
    matches = tuple(
        value for value in snapshot.instrument_valuations
        if value.instrument.identity == proposal.instrument.identity
    )
    if len(matches) != 1:
        raise DomainInvariantError("proposal requires exactly one InstrumentValuation")
    value = matches[0]
    if value.instrument.currency != "USD" or value.current_price.currency != "USD":
        raise DomainInvariantError("Portfolio v1 valuations must use USD")
    return value


def _position(proposal: ProposedPosition, snapshot: PortfolioSnapshot) -> Position | None:
    matches = tuple(
        position for position in snapshot.portfolio.positions
        if position.instrument.identity == proposal.instrument.identity
    )
    if len(matches) > 1:
        raise DomainInvariantError("Portfolio contains duplicate Instrument Position")
    return matches[0] if matches else None


def _quantize(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


def evaluate_one(
    proposal: ProposedPosition,
    snapshot: PortfolioSnapshot,
    parameters: PortfolioParameters | None = None,
) -> PortfolioEvaluationResult:
    active = parameters or PortfolioParameters(currency_quantum=snapshot.portfolio.currency_quantum)
    valuation = _valuation(proposal, snapshot)
    starting = _position(proposal, snapshot)
    reference_capital = snapshot.portfolio.net_liquidation_value.amount
    if reference_capital <= 0:
        raise DomainInvariantError("Portfolio reference capital must be positive")
    metrics = proposal.expected_outcome_metrics
    if metrics.capital_required <= 0:
        raise DomainInvariantError("ExpectedOutcomeMetrics.capital_required must be positive")
    with localcontext() as context:
        context.prec = active.decimal_precision
        raw = proposal.target_allocation * reference_capital / valuation.unit_exposure.amount
        increments = (raw / valuation.quantity_increment).to_integral_value(rounding=ROUND_FLOOR)
        target = increments * valuation.quantity_increment
        start_quantity = starting.quantity if starting else Decimal("0")
        start_direction = starting.direction if starting else None
        evidence = _evidence(proposal.evidence, snapshot.evidence, valuation.evidence)
        rationale = ("target allocation sized against source Portfolio net liquidation value",)
        if start_direction in {None, PositionDirection.LONG} and target == start_quantity:
            result_id = _identity(
                PORTFOLIO_EVALUATION_NAMESPACE,
                PORTFOLIO_ALGORITHM_VERSION,
                snapshot.portfolio_snapshot_id,
                proposal.proposed_position_id,
                PortfolioEvaluationDisposition.NO_CHANGE.value,
                rationale,
                tuple(_evidence_key(item) for item in evidence),
            )
            return PortfolioEvaluationResult(
                result_id,
                PORTFOLIO_ALGORITHM_VERSION,
                snapshot.portfolio_snapshot_id,
                proposal.proposed_position_id,
                PortfolioEvaluationDisposition.NO_CHANGE,
                None,
                rationale,
                evidence,
            )
        loss_rate = abs(metrics.maximum_loss) / metrics.capital_required
        target_exposure = target * valuation.unit_exposure.amount
        projected_loss = _quantize(loss_rate * target_exposure, active.currency_quantum)
        current_long = start_quantity if start_direction is PositionDirection.LONG else Decimal("0")
        cash_change = _quantize(
            -(target - current_long) * valuation.unit_exposure.amount,
            active.currency_quantum,
        )
        delta_inputs = (
            PORTFOLIO_ALGORITHM_VERSION,
            snapshot.portfolio_snapshot_id,
            snapshot.portfolio.portfolio_state_id,
            proposal.proposed_position_id,
            snapshot.portfolio.account_id,
            proposal.instrument.identity.scheme,
            proposal.instrument.identity.value,
            start_direction.value if start_direction else None,
            start_quantity,
            target,
            projected_loss,
            cash_change,
            active.canonical_items(),
            tuple(_evidence_key(item) for item in evidence),
        )
        delta = PortfolioDelta(
            _identity(PORTFOLIO_DELTA_NAMESPACE, delta_inputs),
            PORTFOLIO_ALGORITHM_VERSION,
            PortfolioDeltaKind.PROPOSED,
            snapshot.portfolio_snapshot_id,
            snapshot.portfolio.portfolio_state_id,
            proposal.proposed_position_id,
            None,
            snapshot.portfolio.account_id,
            proposal.instrument,
            MonetaryAmount(projected_loss, "USD"),
            start_direction,
            start_quantity,
            PositionDirection.LONG if target > 0 else None,
            target,
            MonetaryAmount(cash_change, "USD"),
            MonetaryAmount(cash_change, "USD"),
            rationale,
            active.canonical_items(),
            evidence,
        )
        result_id = _identity(
            PORTFOLIO_EVALUATION_NAMESPACE,
            PORTFOLIO_ALGORITHM_VERSION,
            snapshot.portfolio_snapshot_id,
            proposal.proposed_position_id,
            PortfolioEvaluationDisposition.DELTA_PRODUCED.value,
            delta.portfolio_delta_id,
            rationale,
            tuple(_evidence_key(item) for item in evidence),
        )
        return PortfolioEvaluationResult(
            result_id,
            PORTFOLIO_ALGORITHM_VERSION,
            snapshot.portfolio_snapshot_id,
            proposal.proposed_position_id,
            PortfolioEvaluationDisposition.DELTA_PRODUCED,
            delta,
            rationale,
            evidence,
        )


def evaluate_portfolio(
    request: PortfolioEvaluationRequest,
    parameters: PortfolioParameters | None = None,
) -> tuple[PortfolioEvaluationResult, ...]:
    return tuple(evaluate_one(proposal, request.portfolio_snapshot, parameters) for proposal in request.proposed_positions)


def reduction_candidates(
    result: PortfolioEvaluationResult,
    snapshot: PortfolioSnapshot,
) -> tuple[PortfolioDelta, ...]:
    """Return the finite descending quantity lattice below one proposed target."""
    delta = result.proposed_delta
    if delta is None or delta.target_quantity <= 0:
        return ()
    valuation_matches = tuple(
        item for item in snapshot.instrument_valuations
        if item.instrument.identity == delta.instrument.identity
    )
    if len(valuation_matches) != 1:
        raise DomainInvariantError("reduction candidates require one valuation")
    valuation = valuation_matches[0]
    loss_per_exposure = (
        delta.projected_maximum_loss.amount
        / (delta.target_quantity * valuation.unit_exposure.amount)
    )
    current_long = (
        delta.starting_quantity if delta.starting_direction is PositionDirection.LONG else Decimal("0")
    )
    quantities: list[Decimal] = []
    minimum = (
        delta.starting_quantity
        if delta.starting_direction in {None, PositionDirection.LONG}
        else Decimal("0")
    )
    candidate = delta.target_quantity - valuation.quantity_increment
    while candidate > minimum:
        quantities.append(candidate)
        candidate -= valuation.quantity_increment
    candidates: list[PortfolioDelta] = []
    for quantity in quantities:
        cash = _quantize(
            -(quantity - current_long) * valuation.unit_exposure.amount,
            snapshot.portfolio.currency_quantum,
        )
        loss = _quantize(
            loss_per_exposure * quantity * valuation.unit_exposure.amount,
            snapshot.portfolio.currency_quantum,
        )
        candidate_id = _identity(
            PORTFOLIO_DELTA_NAMESPACE,
            delta.portfolio_delta_id,
            quantity,
            cash,
            loss,
        )
        candidates.append(replace(
            delta,
            portfolio_delta_id=candidate_id,
            target_quantity=quantity,
            cash_change=MonetaryAmount(cash, "USD"),
            buying_power_change=MonetaryAmount(cash, "USD"),
            projected_maximum_loss=MonetaryAmount(loss, "USD"),
            rationale=(*delta.rationale, "risk reduction candidate"),
        ))
    return tuple(candidates)
