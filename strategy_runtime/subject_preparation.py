"""Generic, registry/callback-driven subject-first knowledge preparation
(SPRINT-014 S14-PR-05A, Architect checkpoint: twelfth review, item 5 --
"productionize the read-only Earnings preparation without recreating a
strategy-named screening orchestrator ... generic orchestration may expose
sealed provider-neutral evidence and invoke registered strategy bindings;
it must not contain a per-strategy identity comparison or own any single
strategy's own DTE/ATM/analytics policy").

Moves the mechanics an earlier test-only structural-selection harness
stood in for into a real, generic, production-quality seam: run one
subject's phased plan (screening.subject_planning.run_subject_plan) across
whatever SubjectPlanConsumer(s) are registered, then hand the sealed
snapshot plus that one target strategy's own resolved evidence to its own
registered "prepare knowledge mapping" callback, then compose through
strategy_runtime.knowledge_composition.compose_strategy_knowledge exactly
as that harness already proved. No strategy name, no strategy-specific
import, and no branch on strategy_id beyond one generic
SubjectPreparationRegistry.binding_for() lookup.

Still unwired (Architect checkpoint item 8 remains separate, larger,
production-composition-root work): this module has no caller in
asa/scheduled_screening.py or asa/api/screening_routes.py yet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Generic

from domain import MarketCapability, UnknownReason
from market_data.providers import ProviderMetadata
from market_data.resolution import ResolutionPolicy
from market_data.snapshot import MarketSnapshot
from market_data.subject_plan import SubjectAcquisitionPlan
from screening.subject_planning import (
    CapabilityResultReducer,
    ResolvedEvidenceView,
    SubjectPlanConsumer,
    run_subject_plan,
)
from strategy_runtime.knowledge import ReadOnlyStrategyInput, TPayload
from strategy_runtime.knowledge_composition import compose_strategy_knowledge
from strategy_runtime.knowledge_registry import KnowledgeBinding, KnowledgeCompositionRegistry

# A strategy-owned callback: given the sealed snapshot, the final
# provider-neutral projected evidence, this consumer's own phase-two
# DemandExpansion.selections, and the subject string, either build that
# strategy's own KnowledgeMapping (structurally a KnowledgeBinding -- see
# strategy_runtime.knowledge_registry's own docstring for why this is a
# Protocol, never a concrete strategies/-owned import) or return a typed
# UnknownReason for a genuine, expected data gap only discoverable once
# real resolved evidence is in hand. Every DTE/ATM/analytics decision this
# callback makes is entirely strategy-owned; this module never sees it.
PrepareKnowledgeMapping = Callable[
    [MarketSnapshot, ResolvedEvidenceView, tuple[tuple[str, object], ...], str],
    "KnowledgeBinding[TPayload] | UnknownReason",
]


@dataclass(frozen=True, slots=True)
class SubjectPreparationBinding(Generic[TPayload]):
    """One strategy's own subject-first preparation declaration: what to
    plan/demand (a SubjectPlanConsumer, screening-owned but built from
    this strategy's own pure demand/expansion functions) and what to do
    with the plan's own resolved evidence once it seals.
    """

    consumer: SubjectPlanConsumer
    prepare_knowledge_mapping: PrepareKnowledgeMapping[TPayload]


class UnknownSubjectPreparationBindingError(KeyError):
    """Raised when a strategy_id has no registered SubjectPreparationBinding."""


class DuplicateSubjectPreparationBindingError(ValueError):
    """Raised when two entries register the same strategy_id in one
    SubjectPreparationRegistry.
    """


class SubjectPreparationRegistry(Generic[TPayload]):
    """Mirrors strategy_runtime.knowledge_registry.KnowledgeCompositionRegistry's
    own established immutable-constructor shape exactly -- no dynamic
    discovery, no ``.register()`` mutator.
    """

    __slots__ = ("_entries",)

    def __init__(
        self, entries: tuple[tuple[str, SubjectPreparationBinding[TPayload]], ...] = ()
    ) -> None:
        registered: dict[str, SubjectPreparationBinding[TPayload]] = {}
        for strategy_id, binding in entries:
            if strategy_id in registered:
                raise DuplicateSubjectPreparationBindingError(strategy_id)
            registered[strategy_id] = binding
        self._entries = registered

    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def is_registered(self, strategy_id: str) -> bool:
        return strategy_id in self._entries

    def binding_for(self, strategy_id: str) -> SubjectPreparationBinding[TPayload]:
        try:
            return self._entries[strategy_id]
        except KeyError:
            raise UnknownSubjectPreparationBindingError(strategy_id) from None


def prepare_strategy_knowledge(
    plan: SubjectAcquisitionPlan,
    now: datetime,
    registry: SubjectPreparationRegistry[TPayload],
    strategy_id: str,
    *,
    subject: str,
    provider_metadata: tuple[ProviderMetadata, ...],
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy],
    capability_reducer_by_capability: Mapping[MarketCapability, CapabilityResultReducer]
    | None = None,
) -> ReadOnlyStrategyInput[TPayload] | UnknownReason:
    """Run ``registry.binding_for(strategy_id)``'s own consumer through
    one already-built subject plan, hand its resolved evidence to that
    same binding's own ``prepare_knowledge_mapping`` callback, then
    compose the result exactly as
    strategy_runtime.knowledge_composition.compose_strategy_knowledge
    already does for a directly-supplied KnowledgeMapping. Raises
    UnknownSubjectPreparationBindingError (via ``registry.binding_for``)
    for an unregistered strategy_id -- a genuine caller-side defect,
    never a typed UNKNOWN. Returns a typed UnknownReason (never raises
    otherwise) if the binding's own callback returns one, or if
    compose_strategy_knowledge itself does (an unresolved grounding
    resolution).
    """
    binding = registry.binding_for(strategy_id)
    plan_result = run_subject_plan(
        plan,
        now,
        (binding.consumer,),
        provider_metadata=provider_metadata,
        resolution_policy_by_capability=resolution_policy_by_capability,
        capability_reducer_by_capability=capability_reducer_by_capability,
    )
    expansion = plan_result.expansions_by_consumer[binding.consumer.consumer_id]
    if expansion.unknown_reasons:
        # Phase-two expansion itself already found a genuine, expected gap
        # (e.g. no valid expiration pair) -- propagate its own typed
        # reason directly, generically, never rediscovered less precisely
        # downstream by the binding's own callback.
        return expansion.unknown_reasons[0]
    mapping = binding.prepare_knowledge_mapping(
        plan_result.snapshot, plan_result.projected_evidence, expansion.selections, subject
    )
    if isinstance(mapping, UnknownReason):
        return mapping
    knowledge_registry: KnowledgeCompositionRegistry[TPayload] = KnowledgeCompositionRegistry(
        ((strategy_id, mapping),)
    )
    return compose_strategy_knowledge(
        plan_result.snapshot, knowledge_registry, strategy_id, subject=subject
    )
