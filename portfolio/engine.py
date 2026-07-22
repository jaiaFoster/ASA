"""Pure Portfolio Engine calculation owner (ASA-ARCH-006)."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN, localcontext

from domain.canonicalization import serialize_canonical
from domain.execution import (
    ExecutionPlan,
    PlannedOrderSide,
    PortfolioDelta,
    PortfolioDeltaKind,
    PortfolioEvaluationDisposition,
    PortfolioEvaluationResult,
)
from domain.operational import (
    InstrumentValuation,
    MonetaryAmount,
    Portfolio,
    PortfolioEvaluationRequest,
    PortfolioSnapshot,
    Position,
    PositionDirection,
    ProposedPosition,
)
from domain.references import EvidenceReference
from domain.simulation import SimulationMarketData, SimulationResult
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


def apply_simulation(
    plan: ExecutionPlan,
    result: SimulationResult,
    market_data: SimulationMarketData,
) -> tuple[PortfolioDelta, PortfolioSnapshot]:
    """Apply simulated fills as the sole owner of next Portfolio calculations."""
    if result.execution_plan_id != plan.execution_plan_id:
        raise DomainInvariantError("SimulationResult must reference ExecutionPlan")
    if result.market_data_id != market_data.simulation_market_data_id:
        raise DomainInvariantError("SimulationResult must reference SimulationMarketData")
    approved = plan.risk_decision.approved_delta
    if approved is None:
        raise DomainInvariantError("simulation application requires approved delta")
    source = plan.source_snapshot
    portfolio = source.portfolio
    order_by_id = {order.planned_order_id: order for order in plan.planned_orders}
    fills = tuple(sorted(result.simulated_fills, key=lambda item: item.global_fill_sequence))
    target_position = next((
        item for item in portfolio.positions
        if item.instrument.identity == approved.instrument.identity
    ), None)
    direction = target_position.direction if target_position else None
    quantity = target_position.quantity if target_position else Decimal("0")
    average = target_position.average_cost_per_unit.amount if target_position else Decimal("0")
    position_realized = target_position.realized_pnl.amount if target_position else Decimal("0")
    newly_realized = Decimal("0")
    cash_change = Decimal("0")
    last_price: Decimal | None = None
    for fill in fills:
        order = order_by_id[fill.planned_order_id]
        economic = fill.price.amount * order.price_multiplier * fill.quantity
        last_price = fill.price.amount
        if order.side is PlannedOrderSide.BUY:
            if direction not in {None, PositionDirection.LONG}:
                raise DomainInvariantError("BUY cannot increase an uncovered short")
            previous_cost = average * quantity
            quantity += fill.quantity
            average = (previous_cost + fill.price.amount * fill.quantity) / quantity
            direction = PositionDirection.LONG
            cash_change -= economic
        elif order.side is PlannedOrderSide.SELL:
            if direction is not PositionDirection.LONG or fill.quantity > quantity:
                raise DomainInvariantError("SELL requires sufficient long Position")
            realized = (fill.price.amount - average) * order.price_multiplier * fill.quantity
            newly_realized += realized
            position_realized += realized
            quantity -= fill.quantity
            cash_change += economic
            if quantity == 0:
                direction = None
                average = Decimal("0")
        else:
            if direction is not PositionDirection.SHORT or fill.quantity > quantity:
                raise DomainInvariantError("BUY_TO_COVER requires sufficient short Position")
            realized = (average - fill.price.amount) * order.price_multiplier * fill.quantity
            newly_realized += realized
            position_realized += realized
            quantity -= fill.quantity
            cash_change -= economic
            if quantity == 0:
                direction = None
                average = Decimal("0")
    valuation = _valuation_by_identity(source, approved.instrument.identity)
    next_positions = [
        item for item in portfolio.positions
        if item.instrument.identity != approved.instrument.identity
    ]
    if quantity > 0 and direction is not None:
        current = last_price if last_price is not None else valuation.current_price.amount
        unit = current * valuation.price_multiplier
        market_value = quantity * unit
        unrealized = (
            (current - average) if direction is PositionDirection.LONG else (average - current)
        ) * valuation.price_multiplier * quantity
        position_evidence = _evidence(
            valuation.evidence,
            *(fill.evidence for fill in fills),
        )
        next_positions.append(Position(
            _identity("asa.position.v1", approved.instrument.identity.scheme, approved.instrument.identity.value, direction.value, quantity, average, current, market_data.as_of, tuple(_evidence_key(item) for item in position_evidence)),
            portfolio.account_id, approved.instrument, direction, quantity,
            valuation.quantity_increment, MonetaryAmount(average, "USD"),
            MonetaryAmount(current, "USD"), valuation.price_multiplier,
            MonetaryAmount(unit, "USD"), MonetaryAmount(market_value, "USD"),
            MonetaryAmount(market_value, "USD"), MonetaryAmount(position_realized, "USD"),
            MonetaryAmount(unrealized, "USD"), market_data.as_of, position_evidence,
        ))
    next_positions.sort(key=lambda item: (item.instrument.identity.scheme, item.instrument.identity.value))
    next_cash = _quantize(portfolio.cash_balance.amount + cash_change, portfolio.currency_quantum)
    next_buying_power = _quantize(portfolio.buying_power.amount + cash_change, portfolio.currency_quantum)
    if next_buying_power < 0:
        raise DomainInvariantError("simulated transition cannot produce negative buying power")
    gross = sum((item.gross_exposure.amount for item in next_positions), Decimal("0"))
    unrealized_total = sum((item.unrealized_pnl.amount for item in next_positions), Decimal("0"))
    long_value = sum((item.market_value.amount for item in next_positions if item.direction is PositionDirection.LONG), Decimal("0"))
    short_value = sum((item.market_value.amount for item in next_positions if item.direction is PositionDirection.SHORT), Decimal("0"))
    nlv = next_cash + long_value - short_value
    next_realized = portfolio.realized_pnl.amount + newly_realized
    transition_evidence = _evidence(source.evidence, plan.evidence, result.evidence, market_data.evidence)
    state_inputs = (
        portfolio.portfolio_id, portfolio.revision + 1,
        tuple(item.position_id for item in next_positions), next_cash, next_buying_power,
        nlv, gross, next_realized, unrealized_total, tuple(_evidence_key(item) for item in transition_evidence),
    )
    next_portfolio = Portfolio(
        portfolio.portfolio_id, _identity("asa.portfolio.v1", state_inputs), portfolio.revision + 1,
        portfolio.account_id, portfolio.base_currency, portfolio.currency_quantum,
        tuple(next_positions), MonetaryAmount(next_cash, "USD"),
        MonetaryAmount(next_buying_power, "USD"), MonetaryAmount(nlv, "USD"),
        MonetaryAmount(gross, "USD"), MonetaryAmount(next_realized, "USD"),
        MonetaryAmount(unrealized_total, "USD"), portfolio.platform_risk_policies,
        portfolio.policy_activation_evidence,
    )
    next_snapshot = PortfolioSnapshot(
        _identity("asa.portfolio_snapshot.v2", next_portfolio.portfolio_state_id, market_data.as_of, tuple(item.instrument_valuation_id for item in source.instrument_valuations), tuple(_evidence_key(item) for item in transition_evidence)),
        next_portfolio, source.instrument_valuations, market_data.as_of, transition_evidence,
    )
    filled_target = quantity
    loss = Decimal("0")
    if approved.target_quantity:
        loss = _quantize(
            approved.projected_maximum_loss.amount * filled_target / approved.target_quantity,
            portfolio.currency_quantum,
        )
    simulated_delta = replace(
        approved,
        portfolio_delta_id=_identity("asa.portfolio_delta.v1", approved.portfolio_delta_id, result.simulation_result_id, filled_target, cash_change, loss),
        kind=PortfolioDeltaKind.SIMULATED,
        predecessor_delta_id=approved.portfolio_delta_id,
        target_direction=direction,
        target_quantity=filled_target,
        cash_change=MonetaryAmount(_quantize(cash_change, portfolio.currency_quantum), "USD"),
        buying_power_change=MonetaryAmount(_quantize(cash_change, portfolio.currency_quantum), "USD"),
        projected_maximum_loss=MonetaryAmount(loss, "USD"),
        rationale=(*approved.rationale, "derived from deterministic simulated fills"),
        evidence=transition_evidence,
    )
    return simulated_delta, next_snapshot


def _valuation_by_identity(snapshot: PortfolioSnapshot, identity: object) -> InstrumentValuation:
    matches = tuple(item for item in snapshot.instrument_valuations if item.instrument.identity == identity)
    if len(matches) != 1:
        raise DomainInvariantError("portfolio transition requires one valuation")
    return matches[0]
