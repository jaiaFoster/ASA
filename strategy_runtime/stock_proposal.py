"""Canonical provider-neutral stock/ETF opportunity presentation (SP-01).

Projects one immutable screening result of a strategy that declares no option
structure. It never acquires data, sizes a position, estimates a return, or
infers an action the strategy did not emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from strategy_runtime.contract import StrategyContract, StructureKind
from strategy_runtime.result import EvaluationState, UniversalScreeningResult

_ACTION_METRIC = "decision.direction"
_ALLOCATION_METRIC = "decision.target_weight"
_NOT_DEFINED = "not_defined_by_strategy"


class StockProposalStatus(StrEnum):
    ACTIONABLE = "actionable"
    NO_ACTION = "no_action"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StockOpportunityProposal:
    originating_result_identity: str
    instrument: str
    strategy_id: str
    strategy_version: str
    strategy_description: str
    status: StockProposalStatus
    action: str | None
    action_reason: str | None
    signal_verdict: str | None
    evaluation_state: str
    evidence_observed_at: datetime
    signal_metrics: tuple[tuple[str, str], ...]
    allocation: str | None
    allocation_reason: str | None
    unknown_reasons: tuple[str, ...]
    rationale: tuple[str, ...]
    invalidation_notes: tuple[str, ...]
    warnings: tuple[str, ...]
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        if (self.action is None) == (self.action_reason is None):
            raise ValueError("stock proposal action requires exactly one of value or reason")
        if (self.allocation is None) == (self.allocation_reason is None):
            raise ValueError("stock proposal allocation requires exactly one of value or reason")
        if self.status is StockProposalStatus.ACTIONABLE and self.action is None:
            raise ValueError("actionable stock proposal requires a strategy-emitted action")
        if self.status is StockProposalStatus.UNKNOWN and not self.unknown_reasons:
            raise ValueError("unknown stock proposal requires a typed reason")


def build_stock_opportunity_proposal(
    result: UniversalScreeningResult, contract: StrategyContract
) -> StockOpportunityProposal:
    """Project one no-structure result; raise for option-structured contracts."""
    if contract.structure is not StructureKind.NONE:
        raise ValueError("stock proposals apply only to strategies declaring no option structure")
    if contract.strategy_id != result.strategy_id:
        raise ValueError("contract does not belong to the screening result")
    action_value = result.metrics.get(_ACTION_METRIC)
    action = None if action_value is None else str(action_value.native())
    allocation_value = result.metrics.get(_ALLOCATION_METRIC)
    allocation = None if allocation_value is None else str(allocation_value.native())
    evaluated = result.evaluation_state in {EvaluationState.PASS, EvaluationState.NO_SIGNAL}
    if not evaluated:
        status = StockProposalStatus.UNKNOWN
        unknown_reasons = result.blockers or (result.evaluation_state.value,)
    elif (result.verdict or "").upper() == "PASS" and action is not None:
        status = StockProposalStatus.ACTIONABLE
        unknown_reasons = ()
    else:
        status = StockProposalStatus.NO_ACTION
        unknown_reasons = ()
    return StockOpportunityProposal(
        originating_result_identity=result.observation_id,
        instrument=result.symbol,
        strategy_id=result.strategy_id,
        strategy_version=result.strategy_version,
        strategy_description=contract.description,
        status=status,
        action=action,
        action_reason=(
            None
            if action is not None
            else "evaluation_incomplete"
            if not evaluated
            else "no_action_emitted_by_strategy"
        ),
        signal_verdict=result.verdict,
        evaluation_state=result.evaluation_state.value,
        evidence_observed_at=result.observed_at,
        signal_metrics=tuple(
            sorted(
                (name, str(value.native()))
                for name, value in result.metrics.items()
                if not name.startswith(("decision.", "diagnostic.", "gate."))
            )
        ),
        allocation=allocation,
        allocation_reason=None if allocation is not None else _NOT_DEFINED,
        unknown_reasons=tuple(unknown_reasons),
        rationale=(
            contract.description,
            f"{result.strategy_id}@{result.strategy_version} produced "
            f"{result.verdict or result.evaluation_state.value}",
        ),
        invalidation_notes=(_NOT_DEFINED,),
        warnings=result.warnings,
        provenance=result.provenance,
    )
