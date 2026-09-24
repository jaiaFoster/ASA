"""Canonical provider-neutral option trade presentation contract (OP-01).

This module projects existing immutable screening and execution-readiness
truth.  It performs no acquisition, valuation, strategy interpretation, or
broker action.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from strategy_runtime.executable_structures import (
    ExecutableStructureAssessment,
    ExecutableStructureStatus,
)
from strategy_runtime.option_payoff import (
    CALENDAR_LOSS_BOUND_ASSUMPTIONS,
    CALENDAR_LOSS_BOUND_VERSION,
    DeterministicTerminalPayoff,
    PayoffQuantity,
    PayoffQuantityState,
    default_terminal_payoff_grid,
    model_terminal_payoff,
    same_strike_calendar_loss_bound,
)
from strategy_runtime.result import UniversalScreeningResult


class QuantityState(StrEnum):
    SUPPORTED = "supported"
    UNDEFINED = "undefined"
    UNKNOWN = "unknown"


class LiquidityState(StrEnum):
    ACCEPTABLE = "acceptable"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TradeQuantity:
    state: QuantityState
    value: Decimal | None
    reason: str | None

    def __post_init__(self) -> None:
        if self.state is QuantityState.SUPPORTED:
            if self.value is None or self.reason is not None:
                raise ValueError("supported quantity requires a value and no reason")
        elif self.value is not None or not self.reason:
            raise ValueError("undefined/unknown quantity requires a reason and no value")


@dataclass(frozen=True, slots=True)
class TradeProposalLeg:
    canonical_contract_identity: str
    role: str
    buy_or_sell: str
    call_or_put: str
    strike: Decimal
    expiration: date
    quantity: Decimal
    bid: Decimal | None
    ask: Decimal | None
    midpoint: Decimal | None
    actual_delta: Decimal | None
    target_delta: Decimal | None
    quote_observed_at: datetime

    def __post_init__(self) -> None:
        if not self.canonical_contract_identity or not self.role:
            raise ValueError("trade proposal leg identity and role are required")
        if self.quantity <= 0:
            raise ValueError("trade proposal leg quantity must be positive")
        if self.quote_observed_at.tzinfo is None:
            raise ValueError("trade proposal leg quote time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OptionTradeProposal:
    originating_result_identity: str
    underlying: str
    strategy_id: str
    strategy_version: str
    structure: str
    structure_assessment_identity: str
    legs: tuple[TradeProposalLeg, ...]
    modeled_net_debit_or_credit: Decimal
    entry_model_version: str
    entry_calculated_at: datetime
    liquidity: LiquidityState
    capital_required: TradeQuantity
    maximum_loss: TradeQuantity
    maximum_profit: TradeQuantity
    breakeven: TradeQuantity
    evidence_snapshot_identity: str
    constructibility: str
    assumptions: tuple[str, ...]
    rationale: tuple[str, ...]
    risk_notes: tuple[str, ...]
    invalidation_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        identities = tuple(item.canonical_contract_identity for item in self.legs)
        if not identities or len(identities) != len(set(identities)):
            raise ValueError("trade proposal requires unique exact legs")
        if self.entry_calculated_at.tzinfo is None:
            raise ValueError("trade proposal entry time must be timezone-aware")
        if self.constructibility != ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED:
            raise ValueError("trade proposal requires intended constructibility")

    @property
    def identity(self) -> str:
        payload = {
            "assessment": self.structure_assessment_identity,
            "entry": str(self.modeled_net_debit_or_credit),
            "entry_model": self.entry_model_version,
            "legs": [
                [
                    item.canonical_contract_identity,
                    item.role,
                    item.buy_or_sell,
                    str(item.quantity),
                ]
                for item in self.legs
            ],
            "result": self.originating_result_identity,
            "strategy": [self.strategy_id, self.strategy_version],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class TradeProposalUnavailable:
    originating_result_identity: str
    underlying: str
    strategy_id: str
    strategy_version: str
    intended_structure: str
    constructibility: str
    reason_code: str
    blocker_category: str
    user_message: str


def build_option_trade_proposal(
    result: UniversalScreeningResult,
    assessment: ExecutableStructureAssessment,
    terminal_payoff: DeterministicTerminalPayoff | None = None,
) -> OptionTradeProposal | TradeProposalUnavailable:
    """Project one assessment; never infer legs, economics, or policy."""
    if assessment.originating_result_identity != result.observation_id:
        raise ValueError("assessment does not belong to the screening result")
    if (
        terminal_payoff is not None
        and terminal_payoff.structure_assessment_identity != assessment.identity
    ):
        raise ValueError("terminal payoff does not belong to the structure assessment")
    unavailable = _unavailability_reason(assessment)
    if unavailable is not None:
        category, message = classify_trade_blocker(unavailable)
        return TradeProposalUnavailable(
            result.observation_id,
            result.symbol,
            result.strategy_id,
            result.strategy_version,
            assessment.intended_structure_kind.value,
            assessment.status.value,
            unavailable,
            category,
            message,
        )
    assert assessment.modeled_entry_economics is not None
    entry = assessment.modeled_entry_economics
    if terminal_payoff is None:
        # The deterministic bounds depend only on exact strikes and entry, never on
        # the display grid, so every projection (API, tracking) derives them alike.
        derived = model_terminal_payoff(
            assessment=assessment,
            underlying_price_grid=default_terminal_payoff_grid(assessment),
        )
        terminal_payoff = derived if isinstance(derived, DeterministicTerminalPayoff) else None
    calendar_bound = (
        None if terminal_payoff is not None else same_strike_calendar_loss_bound(assessment)
    )
    declared_assumptions = result.metrics.get("decision.assumptions")
    native_assumptions = None if declared_assumptions is None else declared_assumptions.native()
    payoff_assumptions = (
        (f"payoff_model:{terminal_payoff.model_version}",)
        if terminal_payoff is not None
        else (
            f"maximum_loss_model:{CALENDAR_LOSS_BOUND_VERSION}",
            *(f"maximum_loss_assumption:{item}" for item in CALENDAR_LOSS_BOUND_ASSUMPTIONS),
        )
        if calendar_bound is not None
        else ()
    )
    assumptions = tuple(
        sorted(
            {
                "entry_fill:midpoint_modeled_reference_only",
                f"entry_model:{entry.model_version}",
                *payoff_assumptions,
                *(
                    str(item)
                    for item in (native_assumptions if isinstance(native_assumptions, list) else [])
                ),
            }
        )
    )
    not_modeled = TradeQuantity(
        QuantityState.UNKNOWN,
        None,
        "payoff_model_not_attached",
    )
    model_dependent = TradeQuantity(
        QuantityState.UNKNOWN,
        None,
        "later_expiring_leg_value_is_model_dependent",
    )
    if terminal_payoff is not None:
        maximum_loss = _trade_quantity(terminal_payoff.maximum_loss)
        maximum_profit = _trade_quantity(terminal_payoff.maximum_profit)
        breakeven = (
            TradeQuantity(QuantityState.SUPPORTED, terminal_payoff.breakevens[0], None)
            if len(terminal_payoff.breakevens) == 1
            else TradeQuantity(QuantityState.UNDEFINED, None, "multiple_or_no_breakevens")
        )
    elif calendar_bound is not None:
        maximum_loss = _trade_quantity(calendar_bound)
        maximum_profit = model_dependent
        breakeven = model_dependent
    else:
        maximum_loss = maximum_profit = breakeven = not_modeled
    capital_required = (
        maximum_loss
        if entry.modeled_net_debit_or_credit > 0 and maximum_loss.state is QuantityState.SUPPORTED
        else TradeQuantity(
            QuantityState.UNDEFINED if terminal_payoff is not None else QuantityState.UNKNOWN,
            None,
            (
                "capital_requirement_not_defined_for_structure"
                if terminal_payoff is not None
                else "payoff_model_not_attached"
            ),
        )
    )
    payoff_note = (
        "expiration payoff bounds assume the modeled midpoint entry"
        if terminal_payoff is not None
        else "maximum loss is bounded by the modeled debit only if the long leg is held through "
        "the short leg's expiration and exercised or closed promptly if the short leg is "
        "assigned; an early call assignment before an ex-dividend date can add the dividend "
        "owed, and assignment can temporarily require stock-level margin; profit is "
        "model-dependent"
        if calendar_bound is not None
        else "payoff quantities remain unknown until a compatible model is attached"
    )
    return OptionTradeProposal(
        originating_result_identity=result.observation_id,
        underlying=result.symbol,
        strategy_id=result.strategy_id,
        strategy_version=result.strategy_version,
        structure=assessment.intended_structure_kind.value,
        structure_assessment_identity=assessment.identity,
        legs=tuple(
            TradeProposalLeg(
                canonical_contract_identity=item.canonical_contract_identity,
                role=item.leg.role,
                buy_or_sell=("buy" if item.leg.position.value == "long" else "sell"),
                call_or_put=item.leg.contract.option_type.value,
                strike=item.leg.contract.strike,
                expiration=item.leg.contract.expiration,
                quantity=item.leg.quantity,
                bid=item.leg.contract.bid,
                ask=item.leg.contract.ask,
                midpoint=item.midpoint,
                actual_delta=item.leg.contract.delta,
                target_delta=item.target_delta,
                quote_observed_at=item.leg.contract.observed_at,
            )
            for item in assessment.exact_legs
        ),
        modeled_net_debit_or_credit=entry.modeled_net_debit_or_credit,
        entry_model_version=entry.model_version,
        entry_calculated_at=entry.calculated_at,
        liquidity=_liquidity(result),
        capital_required=capital_required,
        maximum_loss=maximum_loss,
        maximum_profit=maximum_profit,
        breakeven=breakeven,
        evidence_snapshot_identity=assessment.evidence_snapshot_identity,
        constructibility=assessment.status.value,
        assumptions=assumptions,
        rationale=(
            f"{result.strategy_id}@{result.strategy_version} produced {result.verdict}",
            f"exact {assessment.intended_structure_kind.value} resolved as intended",
        ),
        risk_notes=(
            "modeled entry is not an executed fill",
            payoff_note,
            *result.warnings,
        ),
        invalidation_notes=("not_defined_by_strategy",),
    )


def _unavailability_reason(assessment: ExecutableStructureAssessment) -> str | None:
    if assessment.status is not ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED:
        return assessment.reason_code or assessment.status.value
    if assessment.modeled_entry_economics is None:
        return "modeled_midpoint_entry_unavailable"
    return None


def classify_trade_blocker(reason_code: str) -> tuple[str, str]:
    """Classify an exact typed reason without changing or hiding that reason."""
    lowered = reason_code.lower()
    mappings = (
        (("stale", "freshness"), "stale_evidence", "Required market evidence is stale."),
        (("earnings",), "earnings_uncertainty", "Earnings clearance is unresolved."),
        (("liquidity", "spread"), "liquidity", "The available market is not liquid enough."),
        (
            ("volatility", "_iv", "iv_"),
            "missing_volatility",
            "Required volatility evidence is unavailable.",
        ),
        (("delta",), "missing_delta", "A required observed option delta is unavailable."),
        (("expiration",), "expiration", "No eligible expiration satisfies the declared structure."),
        (
            ("strike", "compatible_contract"),
            "contract_selection",
            "No exact compatible option contract was found.",
        ),
        (
            ("quote", "midpoint"),
            "missing_quote",
            "A required executable quote or midpoint is unavailable.",
        ),
        (
            ("unsupported",),
            "unsupported_structure",
            "The intended option structure is unsupported.",
        ),
        (
            ("different_structure",),
            "different_structure",
            "Only a different structure is available; ASA will not substitute it.",
        ),
        (
            ("did_not_select_structure",),
            "no_structure_selected",
            "The strategy did not select an option structure.",
        ),
    )
    for needles, category, message in mappings:
        if any(needle in lowered for needle in needles):
            return category, message
    return "unknown", "Execution readiness is unavailable for the typed reason shown."


def _liquidity(result: UniversalScreeningResult) -> LiquidityState:
    values = [
        value.native()
        for key, value in result.metrics.items()
        if key.startswith("gate.") and "liquidity" in key
    ]
    if any(value is False for value in values):
        return LiquidityState.REJECTED
    if values and all(value is True for value in values):
        return LiquidityState.ACCEPTABLE
    return LiquidityState.UNKNOWN


def _trade_quantity(value: PayoffQuantity) -> TradeQuantity:
    if value.state is PayoffQuantityState.SUPPORTED:
        return TradeQuantity(QuantityState.SUPPORTED, value.value, None)
    if value.state is PayoffQuantityState.UNKNOWN:
        return TradeQuantity(QuantityState.UNKNOWN, None, value.reason)
    return TradeQuantity(QuantityState.UNDEFINED, None, value.reason)


def trade_proposal_to_data(
    proposal: OptionTradeProposal | TradeProposalUnavailable,
) -> dict[str, object]:
    """Return the canonical JSON-safe product projection."""
    if isinstance(proposal, TradeProposalUnavailable):
        return {
            "status": "unavailable",
            "originating_result_identity": proposal.originating_result_identity,
            "underlying": proposal.underlying,
            "strategy_id": proposal.strategy_id,
            "strategy_version": proposal.strategy_version,
            "intended_structure": proposal.intended_structure,
            "constructibility": proposal.constructibility,
            "reason_code": proposal.reason_code,
            "blocker_category": proposal.blocker_category,
            "user_message": proposal.user_message,
        }

    def quantity(value: TradeQuantity) -> dict[str, str | None]:
        return {
            "state": value.state.value,
            "value": None if value.value is None else str(value.value),
            "reason": value.reason,
        }

    return {
        "status": "available",
        "proposal_identity": proposal.identity,
        "originating_result_identity": proposal.originating_result_identity,
        "underlying": proposal.underlying,
        "strategy_id": proposal.strategy_id,
        "strategy_version": proposal.strategy_version,
        "structure": proposal.structure,
        "structure_assessment_identity": proposal.structure_assessment_identity,
        "legs": [
            {
                "canonical_contract_identity": item.canonical_contract_identity,
                "role": item.role,
                "buy_or_sell": item.buy_or_sell,
                "call_or_put": item.call_or_put,
                "strike": str(item.strike),
                "expiration": item.expiration.isoformat(),
                "quantity": str(item.quantity),
                "bid": None if item.bid is None else str(item.bid),
                "ask": None if item.ask is None else str(item.ask),
                "midpoint": None if item.midpoint is None else str(item.midpoint),
                "actual_delta": (None if item.actual_delta is None else str(item.actual_delta)),
                "target_delta": (None if item.target_delta is None else str(item.target_delta)),
                "quote_observed_at": item.quote_observed_at.isoformat(),
            }
            for item in proposal.legs
        ],
        "modeled_entry": {
            "modeled_net_debit_or_credit": str(proposal.modeled_net_debit_or_credit),
            "model_version": proposal.entry_model_version,
            "calculated_at": proposal.entry_calculated_at.isoformat(),
            "semantics": "modeled_reference_only",
        },
        "liquidity": proposal.liquidity.value,
        "capital_required": quantity(proposal.capital_required),
        "maximum_loss": quantity(proposal.maximum_loss),
        "maximum_profit": quantity(proposal.maximum_profit),
        "breakeven": quantity(proposal.breakeven),
        "evidence_snapshot_identity": proposal.evidence_snapshot_identity,
        "constructibility": proposal.constructibility,
        "assumptions": list(proposal.assumptions),
        "rationale": list(proposal.rationale),
        "risk_notes": list(proposal.risk_notes),
        "invalidation_notes": list(proposal.invalidation_notes),
    }
