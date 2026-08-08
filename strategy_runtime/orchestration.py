"""Shared production orchestration seam (SPRINT-014 S14-PR-05A, Architect
checkpoint: fourteenth review, "authorized next increment").

The one generic seam both asa/scheduled_screening.py and
asa/api/screening_routes.py call instead of a direct
strategy_runtime.service.refresh() call, wiring together, per subject per
invocation/cycle:

    one CapabilityFulfillmentService (built by the caller, unchanged)
    -> one SubjectAcquisitionPlan       (build_subject_acquisition_access)
    -> one PlanBackedFulfillment        (the same function)
    -> subject-first shadow preparation (prepare_subject_shadow_knowledge,
                                          run once per subject, before any
                                          pair-level refresh)
    -> legacy adapters, closed over the SAME PlanBackedFulfillment
    -> legacy authoritative result      (refresh(), unchanged)
    -> shadow result + parity diagnostic (refresh_with_shadow, per pair)

Legacy stays authoritative: refresh_with_shadow() persists exactly what
refresh() already persists, through the same injected LatestResultRepository
-- a shadow result is never returned as the authoritative result and never
reaches repository.upsert() through this module. No CUTOVER_PASS switch
exists here; that remains S14-PR-06/07's own separate, still-paused work.

Generic, registry/callback-driven throughout: this module imports no
strategy-owned adapter module and contains no ``if strategy_id ==`` branch
of any kind -- ``shadow_registry: SubjectPreparationRegistry`` is the one
extension point a strategy registers itself into (today, only one migrated
strategy does, via its own adapter module's binding-builder function); a
strategy that never registers there is simply never shadowed, with zero
code change here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from domain import MarketCapability, MarketObservation, UnknownReason
from market_data.attempts import AcquisitionAttemptRepository
from market_data.fulfillment import CapabilityFulfillmentService
from market_data.providers import ProviderMetadata
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import PlanBackedFulfillment, SubjectAcquisitionPlan
from screening.subject_planning import CapabilityResultReducer
from strategy_runtime.clock import Clock
from strategy_runtime.context import RuntimeContext
from strategy_runtime.historical_evidence import HistoricalSkewRepository
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.persistence import LatestResultRepository
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult
from strategy_runtime.service import refresh
from strategy_runtime.subject_preparation import (
    SubjectPreparationRegistry,
    prepare_strategy_knowledge,
)
from strategy_runtime.validation import validate_result


@dataclass(frozen=True, slots=True)
class SubjectAcquisitionAccess:
    """One subject's plan-backed acquisition, built once per subject per
    invocation/cycle -- never once per (strategy, subject) pair.
    """

    plan: SubjectAcquisitionPlan
    plan_backed_fulfillment: PlanBackedFulfillment


def build_subject_acquisition_access(
    subject: str,
    fulfillment: CapabilityFulfillmentService,
    *,
    attempt_repository: AcquisitionAttemptRepository,
    plan_id: str,
    clock: Clock,
    maximum_attempts_per_request: int = 2,
) -> SubjectAcquisitionAccess:
    """Wrap an already-built, subject-scoped CapabilityFulfillmentService
    (unchanged, still owning provider selection/fallback/de-duplication)
    in exactly one SubjectAcquisitionPlan and its PlanBackedFulfillment
    adapter. The plan itself durably persists every attempt it makes
    through ``attempt_repository`` (market_data.attempts's own S13-02
    contract) -- this module never records a second, competing attempt
    trail; a caller migrating onto this seam retires its own prior
    per-pair attempt-recording block rather than running both.
    """
    plan = SubjectAcquisitionPlan(
        subject,
        fulfillment,
        attempt_repository=attempt_repository,
        plan_id=plan_id,
        clock=clock,
        maximum_attempts_per_request=maximum_attempts_per_request,
    )
    return SubjectAcquisitionAccess(plan, PlanBackedFulfillment(plan))


def prepare_subject_shadow_knowledge(
    plan: SubjectAcquisitionPlan,
    now: datetime,
    shadow_registry: SubjectPreparationRegistry[object],
    *,
    subject: str,
    provider_metadata: tuple[ProviderMetadata, ...],
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy],
    capability_reducer_by_capability: Mapping[MarketCapability, CapabilityResultReducer]
    | None = None,
) -> dict[str, ReadOnlyStrategyInput[object] | UnknownReason]:
    """Run subject-first preparation once for every strategy_id
    ``shadow_registry`` declares, against the same ``plan`` every legacy
    adapter will also share via PlanBackedFulfillment -- called once per
    subject, before any pair-level refresh_with_shadow() call for that
    subject, never once per pair. Iterates ``shadow_registry.
    strategy_ids()`` generically; never imports or branches on a specific
    strategy identity.

    ``capability_reducer_by_capability`` is forwarded unchanged to
    screening.subject_planning.run_subject_plan (via
    prepare_strategy_knowledge) -- e.g.
    market_data.capability_coalescing.reduce_option_chain_results for a
    subject whose own demands mix expiration discovery with per-expiration
    contract acquisition for OPTION_CHAIN_V1. Caller-supplied, generic:
    this module never registers one itself.
    """
    return {
        strategy_id: prepare_strategy_knowledge(
            plan,
            now,
            shadow_registry,
            strategy_id,
            subject=subject,
            provider_metadata=provider_metadata,
            resolution_policy_by_capability=resolution_policy_by_capability,
            capability_reducer_by_capability=capability_reducer_by_capability,
        )
        for strategy_id in shadow_registry.strategy_ids()
    }


# The envelope/pair identity fields plus the semantic fields two
# UniversalScreeningResults for the same (strategy, symbol) must agree on
# for the shadow path to be considered a match against legacy (Architect
# checkpoint: fourteenth review "shadow comparison contract"; fifteenth
# review corrective item 4: "additionally require pair/envelope identity
# to agree ... a malformed shadow result could theoretically compare as
# match against the wrong pair"). ``observation_id`` is deliberately
# excluded -- the shadow intentionally carries its own run identity
# (_shadow_run_id), never legacy's. Provenance is also excluded --
# richer subject-first provenance is expected, not a parity failure.
_COMPARED_SCALAR_FIELDS: tuple[str, ...] = (
    "strategy_id",
    "strategy_version",
    "symbol",
    "row_type",
    "verdict",
    "evaluation_state",
    "opportunity_id",
    "lifecycle_stage",
    "warnings",
    "observed_at",
)


def _compare_metrics(legacy: UniversalScreeningResult, shadow: UniversalScreeningResult) -> bool:
    """Native score and every graph-derived metric key must match exactly
    (Architect checkpoint: fifteenth review, corrective item 1): a metric
    present on only one side is a parity failure, never silently allowed
    through -- the provenance richer-shadow carve-out does not extend to
    metrics, so a subject-first path that silently drops
    strategy_native_score or a graph-derived metric key is caught here,
    not masked by an intersection-only comparison.
    """
    return legacy.metrics == shadow.metrics


@dataclass(frozen=True, slots=True)
class ShadowParityDiagnostic:
    """Diagnostic-only comparison of one pair's shadow result against its
    own legacy authoritative result -- never persisted, never returned as
    a UniversalScreeningResult itself.

    ``status`` is one of: "match" (every compared field and every shared
    metric key agree), "mismatch" (at least one compared field or shared
    metric key disagrees -- see ``mismatched_fields``), "shadow_unknown"
    (the subject-first path returned a typed UnknownReason -- an expected
    outcome, not an error, recorded explicitly rather than converted into
    an exception or a fabricated result), "shadow_error" (the shadow
    adapter raised; isolated here, never propagated to the caller's own
    authoritative refresh), or "not_shadowed" (strategy_id has no
    registered shadow binding, or this subject's own shadow knowledge was
    never prepared).
    """

    strategy_id: str
    symbol: str
    status: str
    mismatched_fields: tuple[str, ...] = ()
    legacy_verdict: str | None = None
    shadow_verdict: str | None = None
    shadow_unknown_code: str | None = None
    shadow_unknown_demand_ids: tuple[str, ...] = ()
    shadow_error_detail: str | None = None
    shadow_snapshot_id: str | None = None
    shadow_snapshot_digest: str | None = None
    shadow_provenance: tuple[str, ...] = ()

    @property
    def is_match(self) -> bool:
        return self.status == "match"


def _shadow_diagnostic_for_result(
    shadow_result: UniversalScreeningResult, *, legacy_result: UniversalScreeningResult
) -> ShadowParityDiagnostic:
    mismatched = tuple(
        field
        for field in _COMPARED_SCALAR_FIELDS
        if getattr(legacy_result, field) != getattr(shadow_result, field)
    )
    if not _compare_metrics(legacy_result, shadow_result):
        mismatched = (*mismatched, "metrics")
    return ShadowParityDiagnostic(
        strategy_id=legacy_result.strategy_id,
        symbol=legacy_result.symbol,
        status="match" if not mismatched else "mismatch",
        mismatched_fields=mismatched,
        legacy_verdict=legacy_result.verdict,
        shadow_verdict=shadow_result.verdict,
        shadow_snapshot_id=_snapshot_id_from_provenance(shadow_result.provenance),
        shadow_snapshot_digest=_snapshot_digest_from_provenance(shadow_result.provenance),
        shadow_provenance=shadow_result.provenance,
    )


def _snapshot_id_from_provenance(provenance: tuple[str, ...]) -> str | None:
    for entry in provenance:
        if entry.startswith("snapshot_id:"):
            return entry.removeprefix("snapshot_id:")
    return None


def _snapshot_digest_from_provenance(provenance: tuple[str, ...]) -> str | None:
    for entry in provenance:
        if entry.startswith("snapshot_digest:"):
            return entry.removeprefix("snapshot_digest:")
    return None


def _shadow_run_id(strategy_id: str, symbol: str, now: datetime) -> str:
    payload = {"shadow_for": strategy_id, "symbol": symbol, "as_of": now.isoformat()}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _run_shadow(
    shadow_registry: SubjectPreparationRegistry[object],
    shadow_knowledge_by_subject: dict[str, ReadOnlyStrategyInput[object] | UnknownReason],
    legacy_registry: StrategyRegistry[UniversalScreeningResult],
    *,
    legacy_result: UniversalScreeningResult,
    strategy_id: str,
    symbol: str,
    clock: Clock,
    now: datetime,
) -> ShadowParityDiagnostic:
    knowledge_or_unknown = shadow_knowledge_by_subject.get(strategy_id)
    if knowledge_or_unknown is None:
        return ShadowParityDiagnostic(strategy_id=strategy_id, symbol=symbol, status="not_shadowed")
    if isinstance(knowledge_or_unknown, UnknownReason):
        return ShadowParityDiagnostic(
            strategy_id=strategy_id,
            symbol=symbol,
            status="shadow_unknown",
            legacy_verdict=legacy_result.verdict,
            shadow_unknown_code=knowledge_or_unknown.code,
            shadow_unknown_demand_ids=knowledge_or_unknown.demand_ids,
        )
    contract = legacy_registry.contract_for(strategy_id)
    binding = shadow_registry.binding_for(strategy_id)
    shadow_adapter = binding.build_shadow_adapter({symbol: knowledge_or_unknown})
    context = RuntimeContext(
        contract, symbol, clock, _shadow_run_id(strategy_id, symbol, now)
    )
    try:
        shadow_result = shadow_adapter(context)
        # Architect checkpoint: fifteenth review, corrective item 4 --
        # reuse the same generic "declared outputs emitted" check every
        # legacy adapter's own execution already goes through
        # (strategy_runtime.execution._run_one), rather than duplicating
        # it here. A shadow result that fails it is isolated exactly like
        # any other shadow failure, never propagated.
        validate_result(contract, shadow_result)
    except Exception as exc:  # noqa: BLE001 -- isolated shadow failure, never propagated
        return ShadowParityDiagnostic(
            strategy_id=strategy_id,
            symbol=symbol,
            status="shadow_error",
            legacy_verdict=legacy_result.verdict,
            shadow_error_detail=f"{type(exc).__name__}: {exc}",
        )
    return _shadow_diagnostic_for_result(shadow_result, legacy_result=legacy_result)


def refresh_with_shadow(
    legacy_registry: StrategyRegistry[UniversalScreeningResult],
    repository: LatestResultRepository,
    clock: Clock,
    *,
    strategy_id: str,
    symbol: str,
    observations: Callable[[], tuple[MarketObservation, ...]],
    historical_skew_repository: HistoricalSkewRepository | None = None,
    shadow_registry: SubjectPreparationRegistry[object] | None = None,
    shadow_knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object] | UnknownReason]
    | None = None,
    now: datetime | None = None,
) -> tuple[UniversalScreeningResult, ShadowParityDiagnostic | None]:
    """The one orchestration seam both production roots call, replacing a
    direct strategy_runtime.service.refresh() call.

    Always runs and returns exactly what refresh() already would --
    ``legacy_registry`` is expected to already be built with adapters
    closed over this subject's own PlanBackedFulfillment (built by
    build_subject_acquisition_access(), used identically to how a raw
    CapabilityFulfillmentService was closed over before), so legacy FF/
    Skew/Earnings execute unchanged through the same plan subject-first
    preparation already populated.

    If (and only if) ``shadow_registry`` is supplied and ``strategy_id``
    is registered in it, and ``shadow_knowledge_by_subject`` (built once
    per subject by prepare_subject_shadow_knowledge(), never re-prepared
    here) already carries this subject's own entry for it, also builds a
    diagnostic-only shadow result and compares it against the legacy
    result -- returned as the second tuple element, never persisted and
    never substituted for the first. A shadow failure of any kind (typed
    UnknownReason, an unexpected exception) is recorded in the returned
    diagnostic, never raised and never allowed to affect the legacy
    result this function still returns and the caller still persists.
    """
    result = refresh(
        legacy_registry,
        repository,
        clock,
        strategy_id=strategy_id,
        symbol=symbol,
        observations=observations,
        historical_skew_repository=historical_skew_repository,
    )
    if (
        shadow_registry is None
        or shadow_knowledge_by_subject is None
        or not shadow_registry.is_registered(strategy_id)
    ):
        return result, None
    diagnostic = _run_shadow(
        shadow_registry,
        dict(shadow_knowledge_by_subject),
        legacy_registry,
        legacy_result=result,
        strategy_id=strategy_id,
        symbol=symbol,
        clock=clock,
        now=now or clock.now(),
    )
    return result, diagnostic
