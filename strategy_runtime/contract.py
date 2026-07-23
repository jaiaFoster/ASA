"""Declarative Strategy Contract (SPRINT-009/EPIC-2).

A StrategyContract is a strategy's complete self-description: metadata,
data requirements, lifecycle model, option structure, and output shape.
It is the one thing the universal runtime (EPIC-1, built on top of this
module) reads to execute a strategy, and the one thing a new strategy's
author must write. No runtime decision should ever need to know a
strategy_id by name -- every runtime decision this sprint's
architecture_principles call for ("runtime contains no strategy-named
conditional") should be derivable from a StrategyContract's own fields
instead.

This module deliberately does not execute anything, register anything, or
know about any specific strategy (earnings_calendar, skew_momentum_vertical,
forward_factor, or otherwise) -- registration and discovery are EPIC-1's own
job. See tests/strategy_runtime/test_migration_target_contracts.py for
those three strategies' own draft contracts, proving this schema is
sufficient to describe each of them, without wiring any of them into a
runtime yet (EPIC-7's own job).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain import MarketCapability
from strategy_runtime.errors import StrategyContractError


def _normalized_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise StrategyContractError(f"{owner}.{field_name} must be non-empty normalized text")


class RequirementCategory(str, Enum):
    MARKET_DATA = "market_data"
    OPTION_DATA = "option_data"
    EARNINGS = "earnings"
    FUNDAMENTALS = "fundamentals"
    TECHNICALS = "technicals"
    MACRO = "macro"
    CUSTOM = "custom"


# Categories whose data is acquired through the existing, canonical
# MarketCapability system (domain/market_data.py, market_data/) -- a
# DataRequirement filed under one of these must name at least one real
# capability, not merely a category label. fundamentals/technicals/macro
# are declarable today (so a future strategy can adopt one without a
# contract-schema change) but have no capability system behind them yet;
# custom requirements identify themselves by name instead of a capability.
_CAPABILITY_BACKED_CATEGORIES = frozenset(
    {RequirementCategory.MARKET_DATA, RequirementCategory.OPTION_DATA, RequirementCategory.EARNINGS}
)


@dataclass(frozen=True, slots=True)
class DataRequirement:
    category: RequirementCategory
    capabilities: tuple[MarketCapability, ...] = ()
    identifier: str | None = None

    def __post_init__(self) -> None:
        if self.category in _CAPABILITY_BACKED_CATEGORIES and not self.capabilities:
            raise StrategyContractError(
                f"a {self.category.value!r} DataRequirement must declare at least one "
                "MarketCapability"
            )
        if self.category is RequirementCategory.CUSTOM and not self.identifier:
            raise StrategyContractError("a custom DataRequirement must declare an identifier")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise StrategyContractError("DataRequirement.capabilities must be unique")
        if self.identifier is not None:
            _normalized_text(self.identifier, "DataRequirement", "identifier")


class LifecycleModel(str, Enum):
    NONE = "none"
    OPPORTUNITY = "opportunity"


@dataclass(frozen=True, slots=True)
class LifecycleDeclaration:
    """NONE means the strategy has no persistent identity across
    observations -- each evaluation stands alone, matching every strategy
    this repository has ever run before this sprint. OPPORTUNITY means the
    strategy tracks a specific opportunity's evolution across repeated
    observations (EPIC-5's own generalization of the mature Stonk Calendar
    implementation's lifecycle) and must declare which states that
    opportunity can be in and what kind of thing is being observed.
    """

    lifecycle_model: LifecycleModel
    supported_states: tuple[str, ...] = ()
    observation_type: str | None = None

    def __post_init__(self) -> None:
        if self.lifecycle_model is LifecycleModel.NONE:
            if self.supported_states or self.observation_type is not None:
                raise StrategyContractError(
                    "a NONE LifecycleDeclaration must not declare supported_states or "
                    "observation_type"
                )
            return
        if not self.supported_states:
            raise StrategyContractError(
                "an OPPORTUNITY LifecycleDeclaration must declare at least one supported state"
            )
        if len(set(self.supported_states)) != len(self.supported_states):
            raise StrategyContractError("LifecycleDeclaration.supported_states must be unique")
        for state in self.supported_states:
            _normalized_text(state, "LifecycleDeclaration", "supported_states entry")
        if not self.observation_type:
            raise StrategyContractError(
                "an OPPORTUNITY LifecycleDeclaration must declare its observation_type"
            )
        _normalized_text(self.observation_type, "LifecycleDeclaration", "observation_type")


NO_LIFECYCLE = LifecycleDeclaration(LifecycleModel.NONE)


class StrategyCapability(str, Enum):
    """Runtime capabilities a strategy opts into (SPRINT-009R/EPIC-R1). Each
    entry here is cross-checked against this same contract's other
    declarations in __post_init__ below -- a capability is never merely
    decorative, it is always backed by a consistent structural declaration
    elsewhere in the contract, so the runtime can derive behavior from
    ``capabilities`` alone without re-deriving it from ``outputs``,
    ``lifecycle``, or ``structure`` separately.
    """

    LIFECYCLE = "lifecycle"
    HISTORY = "history"
    ECONOMICS = "economics"
    RECOMMENDATIONS = "recommendations"
    OPTION_STRUCTURES = "option_structures"
    MULTIPLE_RESULTS = "multiple_results"
    INCREMENTAL_REFRESH = "incremental_refresh"


class StructureKind(str, Enum):
    NONE = "none"
    VERTICAL = "vertical"
    CALENDAR = "calendar"
    CUSTOM = "custom"


class OutputKind(str, Enum):
    METRICS = "metrics"
    ECONOMICS = "economics"
    LIFECYCLE = "lifecycle"
    RECOMMENDATION_SUPPORT = "recommendation_support"


@dataclass(frozen=True, slots=True)
class StrategyContract:
    strategy_id: str
    version: str
    category: str
    description: str
    requirements: tuple[DataRequirement, ...]
    lifecycle: LifecycleDeclaration
    structure: StructureKind
    outputs: tuple[OutputKind, ...]
    capabilities: tuple[StrategyCapability, ...] = ()

    def __post_init__(self) -> None:
        for name in ("strategy_id", "version", "category", "description"):
            _normalized_text(getattr(self, name), "StrategyContract", name)
        if not self.requirements:
            raise StrategyContractError("StrategyContract.requirements cannot be empty")
        if len(set(self.requirements)) != len(self.requirements):
            raise StrategyContractError(
                "StrategyContract.requirements must not repeat an identical requirement"
            )
        if not self.outputs:
            raise StrategyContractError("StrategyContract.outputs cannot be empty")
        if len(set(self.outputs)) != len(self.outputs):
            raise StrategyContractError("StrategyContract.outputs must be unique")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise StrategyContractError("StrategyContract.capabilities must be unique")
        if (
            OutputKind.LIFECYCLE in self.outputs
            and self.lifecycle.lifecycle_model is LifecycleModel.NONE
        ):
            raise StrategyContractError(
                "a StrategyContract declaring LIFECYCLE output must declare a non-NONE "
                "lifecycle_model"
            )
        self._check_capability_consistency()

    def _check_capability_consistency(self) -> None:
        """Lifecycle/structure/capability consistency (EPIC-R1's own three
        runtime_validation entries that are knowable from the contract
        alone, without an execution having happened yet) -- a *declared*
        capability must always be backed by the specific other declaration
        it presupposes. Deliberately one-directional: a contract that omits
        ``capabilities`` entirely (every contract written before EPIC-R1
        added this field) is not itself inconsistent -- ``capabilities`` is
        an additive, opt-in declaration, not a second mandatory encoding of
        ``lifecycle``/``structure``/``outputs``. Only a capability claim
        that outruns its backing is ever rejected.
        """
        has_lifecycle_model = self.lifecycle.lifecycle_model is not LifecycleModel.NONE
        declares_lifecycle_output = OutputKind.LIFECYCLE in self.outputs
        if StrategyCapability.LIFECYCLE in self.capabilities and not (
            has_lifecycle_model and declares_lifecycle_output
        ):
            raise StrategyContractError(
                "StrategyCapability.LIFECYCLE requires a non-NONE lifecycle_model and "
                "OutputKind.LIFECYCLE in outputs"
            )
        if (
            StrategyCapability.HISTORY in self.capabilities
            and StrategyCapability.LIFECYCLE not in self.capabilities
        ):
            raise StrategyContractError(
                "StrategyCapability.HISTORY requires StrategyCapability.LIFECYCLE -- history "
                "tracks a lifecycle-tracked opportunity's observations over time"
            )
        if (
            StrategyCapability.ECONOMICS in self.capabilities
            and OutputKind.ECONOMICS not in self.outputs
        ):
            raise StrategyContractError(
                "StrategyCapability.ECONOMICS requires OutputKind.ECONOMICS in outputs"
            )
        if (
            StrategyCapability.RECOMMENDATIONS in self.capabilities
            and OutputKind.RECOMMENDATION_SUPPORT not in self.outputs
        ):
            raise StrategyContractError(
                "StrategyCapability.RECOMMENDATIONS requires OutputKind.RECOMMENDATION_SUPPORT "
                "in outputs"
            )
        if (
            StrategyCapability.OPTION_STRUCTURES in self.capabilities
            and self.structure is StructureKind.NONE
        ):
            raise StrategyContractError(
                "StrategyCapability.OPTION_STRUCTURES requires a non-NONE structure"
            )

    def requirements_in(self, category: RequirementCategory) -> tuple[DataRequirement, ...]:
        return tuple(item for item in self.requirements if item.category is category)

    def required_capabilities(self) -> tuple[MarketCapability, ...]:
        """Every distinct MarketCapability this contract's requirements
        name, across every capability-backed category, deterministically
        ordered. The single place a future EPIC-1 execution pipeline (or
        EPIC-3's shared data planner) should read a strategy's capability
        needs from -- never re-deriving them from a strategy's own
        adapter code.
        """
        seen: dict[MarketCapability, None] = {}
        for requirement in self.requirements:
            for capability in requirement.capabilities:
                seen[capability] = None
        return tuple(sorted(seen, key=lambda item: item.value))
