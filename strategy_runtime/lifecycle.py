"""Universal Opportunity Model (SPRINT-009/EPIC-5).

Generalizes the lifecycle/verdict/opportunity-identity concepts the mature
Stonk Calendar implementation already has
(/Users/jaiafoster/Claude/stonk/app/services/) into strategy-agnostic
infrastructure -- the engine, not any specific strategy's transition
rules. Reconciling exactly which stages Calendar moves through and when
is EPIC-7's own migration job; this module only guarantees the engine
those rules run on is generic, and enforces the one thing that must be
true regardless of which strategy uses it: a lifecycle_stage a strategy
reports must be one its own StrategyContract actually declared
(strategy_runtime.contract.LifecycleDeclaration.supported_states) --
never invented ad hoc at observation time.

compute_opportunity_id() is deliberately independent of any one
observation or run: strategy_runtime.result.compute_observation_id()
identifies *this* observation event; this function identifies the
*opportunity being observed*, which must stay the same across many
separate observations over time for history (EPIC-8) to mean anything.
The caller supplies whatever fields make an opportunity the same
opportunity for its own strategy (e.g. earnings_calendar's own confirmed
earnings date) -- this module has no opinion on what those fields are,
only that they are hashed the same deterministic way every other identity
in this sprint already is.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from strategy_runtime.contract import LifecycleModel, StrategyContract
from strategy_runtime.errors import StrategyContractError


def compute_opportunity_id(strategy_id: str, symbol: str, *identity_components: str) -> str:
    """Deterministic, stable identity for one tracked opportunity --
    reproducible for identical inputs, matching the same sha256-hash
    convention every other identity in this sprint already uses
    (strategy_runtime.execution's own run_id,
    strategy_runtime.result.compute_observation_id()). Two observations
    of the same real-world opportunity must call this with the same
    identity_components every time; two observations of genuinely
    different opportunities (e.g. two different confirmed earnings dates
    for the same symbol) must not.
    """
    payload = {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "identity_components": list(identity_components),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class RecommendedAction(str, Enum):
    """The vocabulary strategy_runtime.result.UniversalScreeningResult's
    own recommendation_state field holds as a string
    (RecommendedAction.MONITOR.value, etc.) -- kept as a real enum here,
    not a bare string, so a strategy author picks from a closed,
    documented set rather than inventing ad hoc action names per
    strategy. Deliberately not a ranking or priority order across
    actions -- this sprint's own non_goals rule out cross-strategy
    ranking; MONITOR is not "worse" than ENTER, only different.
    """

    MONITOR = "monitor"
    ENTER = "enter"
    HOLD = "hold"
    EXIT = "exit"
    NO_ACTION = "no_action"


@dataclass(frozen=True, slots=True)
class OpportunityObservation:
    """One point-in-time snapshot in a tracked opportunity's evolution --
    the unit strategy_runtime.result.UniversalScreeningResult's own
    lifecycle-related fields (opportunity_id, lifecycle_stage) already
    carry on a single result, gathered here as their own type so EPIC-8
    (Persistence & History) has one clear unit to append to an
    opportunity's history, rather than persisting a full
    UniversalScreeningResult (with its metrics/economics namespaces) for
    every historical point.
    """

    opportunity_id: str
    strategy_id: str
    symbol: str
    lifecycle_stage: str
    verdict: str
    recommended_action: RecommendedAction
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class OpportunityHistory:
    """An ordered, append-only sequence of observations for one
    opportunity_id -- ordered by observed_at, oldest first, matching
    "history replay" (EPIC-8's own acceptance criterion: a caller can
    reconstruct an opportunity's evolution from persisted observations).
    """

    opportunity_id: str
    observations: tuple[OpportunityObservation, ...]

    def __post_init__(self) -> None:
        if not self.observations:
            raise ValueError("OpportunityHistory requires at least one observation")
        if any(item.opportunity_id != self.opportunity_id for item in self.observations):
            raise ValueError(
                "OpportunityHistory.observations must all share the same opportunity_id"
            )
        ordered = tuple(sorted(self.observations, key=lambda item: item.observed_at))
        object.__setattr__(self, "observations", ordered)

    @property
    def current(self) -> OpportunityObservation:
        return self.observations[-1]

    def append(self, observation: OpportunityObservation) -> OpportunityHistory:
        if observation.opportunity_id != self.opportunity_id:
            raise ValueError("appended observation must share this history's own opportunity_id")
        return OpportunityHistory(self.opportunity_id, (*self.observations, observation))


def validate_lifecycle_stage(contract: StrategyContract, stage: str) -> None:
    """The one guardrail that keeps this engine strategy-agnostic: a
    reported lifecycle_stage must be one the strategy's own contract
    actually declared, for a contract that declares lifecycle support at
    all. Raises for a NONE-lifecycle contract (nothing to validate a
    stage against) or an undeclared stage -- never silently accepts an
    ad hoc value.
    """
    if contract.lifecycle.lifecycle_model is LifecycleModel.NONE:
        raise StrategyContractError(
            f"{contract.strategy_id!r} declares no lifecycle model; it cannot report a "
            "lifecycle_stage"
        )
    if stage not in contract.lifecycle.supported_states:
        raise StrategyContractError(
            f"{stage!r} is not a lifecycle_stage {contract.strategy_id!r} declared "
            f"(declared: {contract.lifecycle.supported_states})"
        )
