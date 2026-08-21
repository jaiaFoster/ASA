"""Shared production orchestration seam (SPRINT-014 S14-PR-05A, Architect
checkpoint: nineteenth review, "CUTOVER_PASS ... implement the
already-approved PR-05 cutover mechanism").

The one generic seam both asa/scheduled_screening.py and
asa/api/screening_routes.py call instead of a direct
strategy_runtime.service.refresh() call, wiring together, per subject per
invocation/cycle:

    one CapabilityFulfillmentService (built by the caller, unchanged)
    -> one SubjectAcquisitionPlan       (build_subject_acquisition_access)
    -> one PlanBackedFulfillment        (the same function)
    -> subject-first preparation        (prepare_subject_shadow_knowledge,
                                          run once per subject, before any
                                          pair-level refresh)
    -> legacy adapters, closed over the SAME PlanBackedFulfillment
    -> refresh_with_shadow(), per pair:
       * strategy_id has NO registered CutoverPolicy entry (today: FF,
         Skew, and Earnings before its own entry exists) -- unchanged:
         legacy authoritative result (refresh()), plus an optional shadow
         result + parity diagnostic if also shadow-registered.
       * strategy_id HAS a CutoverPolicy entry, currently pointing at
         legacy (rollback) -- same as above: legacy authoritative, shadow
         comparison still runs (an operator can flip back to subject-first
         at any time with zero data migration).
       * strategy_id HAS a CutoverPolicy entry pointing at subject-first
         (cut over) -- subject-first's own already-prepared knowledge
         becomes authoritative; legacy is never invoked at all, and no
         shadow comparison runs (Architect checkpoint: nineteenth review,
         "do not run both authoritative paths after cutover merely to
         preserve shadowing").

Legacy stays the ONLY historically-authoritative path until a strategy's
own CutoverPolicy entry says otherwise; refresh_with_shadow() still
persists exactly what its own selected path computes, through the same
injected LatestResultRepository -- a non-selected path's own result is
never returned as authoritative and never reaches repository.upsert()
through this module.

Generic, registry/callback-driven throughout: this module imports no
strategy-owned adapter module and contains no ``if strategy_id ==`` branch
of any kind -- ``shadow_registry: SubjectPreparationRegistry`` and
``cutover_policy: CutoverPolicy`` are the two registered, data-driven
extension points a strategy's own composition root opts it into (today,
only one migrated strategy is registered in either); a strategy that
never registers in shadow_registry is simply never shadowed, and one
absent from cutover_policy simply never has its authoritative path
selected here, with zero code change in this module either way.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

from domain import MarketCapability, MarketObservation, UnknownReason
from market_data.attempts import AcquisitionAttemptRepository
from market_data.fulfillment import CapabilityFulfillmentResult, CapabilityFulfillmentService
from market_data.providers import CapabilityRequest, ProviderMetadata
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import PlanBackedFulfillment, SubjectAcquisitionPlan
from screening.subject_planning import CapabilityResultReducer
from strategy_runtime.clock import Clock
from strategy_runtime.context import RuntimeContext
from strategy_runtime.historical_evidence import HistoricalSkewRepository
from strategy_runtime.knowledge import ReadOnlyStrategyInput
from strategy_runtime.persistence import LatestResultRepository
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)
from strategy_runtime.service import refresh
from strategy_runtime.subject_preparation import (
    PreparedSubjectKnowledge,
    SubjectPreparationBinding,
    SubjectPreparationRegistry,
    prepare_subject_knowledge,
    prepare_subject_knowledge_with_temporal,
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


@dataclass(slots=True)
class TouchedResultFulfillment:
    """Wraps one pair's own PlanBackedFulfillment, recording every
    CapabilityFulfillmentResult it itself returns -- freshly resolved or
    an already-resolved plan-cache hit alike -- into ``touched`` (Architect
    checkpoint: seventeenth review, "record the provider-neutral
    CapabilityFulfillmentResult returned for each PlanBackedFulfillment.
    fulfill() invocation, including plan-cache hits").

    Both production roots share one raw CapabilityFulfillmentService per
    subject across every consumer this cycle/invocation -- every legacy
    pair AND subject-first shadow preparation, which resolves directly
    through SubjectAcquisitionPlan.resolve(), never through a
    PlanBackedFulfillment wrapper at all. A caller builds one fresh
    instance of this class per pair, closes that pair's own legacy
    strategy registry over THIS wrapper (never the raw
    PlanBackedFulfillment or CapabilityFulfillmentService directly), and
    derives that pair's own observations callback from ``touched`` via
    touched_observations() below -- so temporal metadata for one
    strategy's own result reflects only capability requests that
    strategy's own legacy execution itself actually resolved or reused,
    never evidence some OTHER consumer sharing the same underlying plan
    (shadow preparation, or an earlier/later pair sharing this subject)
    separately acquired for itself. strategy_runtime.orchestration.
    _observations_relevant_to's own capability filter still applies on
    top of this -- narrower provenance, not a replacement for it.

    Deliberately not frozen: a per-call-site accumulator, not an
    identity-bearing value object the way PlanBackedFulfillment itself is.
    Never carried on RuntimeContext (I-09) and never branches on strategy
    identity -- built once per pair by the caller, exactly like
    PlanBackedFulfillment itself already is.
    """

    plan_backed_fulfillment: PlanBackedFulfillment
    touched: list[CapabilityFulfillmentResult] = field(default_factory=list)

    def fulfill(
        self, request: CapabilityRequest, *, required: bool = True
    ) -> CapabilityFulfillmentResult:
        result = self.plan_backed_fulfillment.fulfill(request, required=required)
        self.touched.append(result)
        return result


def touched_observations(tracker: TouchedResultFulfillment) -> tuple[MarketObservation, ...]:
    """The provider-neutral observations flattened from exactly what
    ``tracker`` itself returned to its own caller(s) -- see
    TouchedResultFulfillment's own docstring for why this, not
    market_data.observations_from_fulfillment's own whole-service flatten,
    is what an observations callback passed into refresh_with_shadow
    should be built from.
    """
    return tuple(
        observation for result in tracker.touched for observation in result.observations
    )


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
    strategy_ids: tuple[str, ...] | None = None,
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
    return prepare_subject_knowledge(
        plan,
        now,
        (
            shadow_registry
            if strategy_ids is None
            else shadow_registry.restricted_to(strategy_ids)
        ),
        subject=subject,
        provider_metadata=provider_metadata,
        resolution_policy_by_capability=resolution_policy_by_capability,
        capability_reducer_by_capability=capability_reducer_by_capability,
    )


def prepare_subject_shadow_knowledge_with_temporal(
    plan: SubjectAcquisitionPlan,
    now: datetime,
    shadow_registry: SubjectPreparationRegistry[object],
    *,
    subject: str,
    provider_metadata: tuple[ProviderMetadata, ...],
    resolution_policy_by_capability: dict[MarketCapability, ResolutionPolicy],
    capability_reducer_by_capability: Mapping[MarketCapability, CapabilityResultReducer]
    | None = None,
    strategy_ids: tuple[str, ...] | None = None,
) -> PreparedSubjectKnowledge:
    """Prepare knowledge and consumer-scoped evidence from one sealed snapshot."""
    return prepare_subject_knowledge_with_temporal(
        plan,
        now,
        (
            shadow_registry
            if strategy_ids is None
            else shadow_registry.restricted_to(strategy_ids)
        ),
        subject=subject,
        provider_metadata=provider_metadata,
        resolution_policy_by_capability=resolution_policy_by_capability,
        capability_reducer_by_capability=capability_reducer_by_capability,
    )


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


def _observations_relevant_to(
    strategy_id: str,
    legacy_registry: StrategyRegistry[UniversalScreeningResult],
    observations: Callable[[], tuple[MarketObservation, ...]],
) -> Callable[[], tuple[MarketObservation, ...]]:
    """Scope a caller-supplied observations callback down to only the
    MarketCapability values ``strategy_id`` itself declares in its own
    StrategyContract.requirements (Architect checkpoint: sixteenth review,
    "if the existing broad observations callback causes cross-strategy
    shadow evidence to contaminate their temporal metadata, fix that at
    the generic orchestration/evidence boundary").

    Both production roots share one raw CapabilityFulfillmentService per
    subject across every consumer this cycle/invocation -- every legacy
    pair AND, now, subject-first shadow preparation -- and their own
    ``observations`` callback (typically
    market_data.observations_from_fulfillment) flattens *everything* that
    service has ever completed, unscoped by who asked for it.
    strategy_runtime.service._temporal_metadata is deliberately generic
    and applies no relevance filter of its own (it takes max/min effective
    times and per-observation freshness decisions over whatever tuple it
    is given), so an unfiltered callback would let one strategy's own
    irrelevant evidence -- e.g. one migrated strategy's own single-purpose
    calendar-event observation, of a capability no other strategy declares
    -- silently shift a completely unrelated strategy's own
    observed_at/age/freshness/usability. Filtering here, once, at this
    shared seam, is correct for every caller rather than requiring each
    production root to duplicate it.

    Filters by *capability relevance*, never by *when* an observation was
    actually resolved -- a plan-cache hit reused from an earlier pair or
    from shadow preparation remains included exactly like a freshly
    acquired one, which a "since this pair started" slice would wrongly
    exclude.
    """
    declared_capabilities = frozenset(
        capability
        for requirement in legacy_registry.contract_for(strategy_id).requirements
        for capability in requirement.capabilities
    )

    def _scoped() -> tuple[MarketObservation, ...]:
        return tuple(
            observation
            for observation in observations()
            if observation.capability in declared_capabilities
        )

    return _scoped


@dataclass(frozen=True, slots=True)
class CutoverPolicy:
    """Per-strategy authoritative-path selection for a strategy that has
    already passed its own CUTOVER_PASS gate (Architect checkpoint:
    nineteenth review, "one shared cutover policy owner used identically
    by scheduled and API roots ... registration/policy binding remains
    the extension mechanism").

    Membership in ``subject_first_by_strategy_id`` means "this strategy's
    own authoritative path is now operator-selected, not shadow-compared
    here" -- the boolean value picks legacy (False, the bounded rollback
    path SPRINT-014 itself requires stays available) or subject-first
    (True). A strategy_id with NO entry here (the default, empty policy)
    keeps refresh_with_shadow()'s own pre-cutover behavior completely
    unchanged: legacy authoritative, plus an optional shadow comparison
    if it is also shadow-registered -- exactly today's behavior for every
    strategy that has not yet reached its own CUTOVER_PASS gate.

    Built once per invocation/cycle by a single shared owner both
    production roots call identically (strategy_runtime.adapters.
    build_migrated_cutover_policy) -- never two independently-constructed,
    route-specific switches.
    """

    subject_first_by_strategy_id: Mapping[str, bool] = field(default_factory=dict)

    def is_cut_over(self, strategy_id: str) -> bool:
        return self.subject_first_by_strategy_id.get(strategy_id, False)


def _missing_data_result(
    context: RuntimeContext, symbol: str, reason: UnknownReason
) -> UniversalScreeningResult:
    """The authoritative-subject-first path's own projection for a typed
    evidence gap subject-first preparation itself already discovered
    (Architect checkpoint: nineteenth review: subject-first evaluation
    "must perform zero acquisition of its own" -- falling back to legacy
    execution here would both violate that and give legacy an execution
    call the cutover-enabled mode must never make). Generic: reads only
    the UnknownReason's own typed code/demand_ids, never a strategy
    identity, so this applies identically to any future strategy that
    registers a CutoverPolicy entry.
    """
    return UniversalScreeningResult(
        strategy_id=context.contract.strategy_id,
        strategy_version=context.contract.version,
        symbol=symbol,
        observation_id=compute_observation_id(
            context.run_id, context.contract.strategy_id, symbol
        ),
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict=None,
        evaluation_state=EvaluationState.MISSING_DATA,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality=None,
        metrics={},
        economics={},
        blockers=(
            f"typed unknown evidence gap: {reason.code}"
            + (f" ({reason.detail})" if reason.detail else ""),
        ),
        warnings=(),
        provenance=(
            f"unknown:{reason.code}",
            *(f"demand:{demand_id}" for demand_id in reason.demand_ids),
        ),
        observed_at=context.clock.now(),
    )


def _authoritative_subject_first_adapter(
    binding: SubjectPreparationBinding[object],
    knowledge_or_unknown: ReadOnlyStrategyInput[object] | UnknownReason,
    symbol: str,
) -> Callable[[RuntimeContext], UniversalScreeningResult]:
    """The one adapter cutover-authoritative mode registers in place of
    the legacy adapter -- a pure projection over already-prepared
    knowledge (or a typed gap already-prepared), performing zero
    acquisition of its own either way.
    """
    if isinstance(knowledge_or_unknown, UnknownReason):

        def _missing_data_adapter(context: RuntimeContext) -> UniversalScreeningResult:
            return _missing_data_result(context, symbol, knowledge_or_unknown)

        return _missing_data_adapter
    return binding.build_shadow_adapter({symbol: knowledge_or_unknown})


def _cutover_authoritative_adapter(
    cutover_policy: CutoverPolicy | None,
    shadow_registry: SubjectPreparationRegistry[object] | None,
    shadow_knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object] | UnknownReason]
    | None,
    strategy_id: str,
    symbol: str,
) -> Callable[[RuntimeContext], UniversalScreeningResult] | None:
    """None unless ``strategy_id`` is cut over AND its already-prepared
    shadow knowledge for this subject is actually available -- in every
    other case refresh_with_shadow() falls straight through to its
    existing, unchanged legacy(+optional shadow) behavior.
    """
    if cutover_policy is None or shadow_registry is None:
        return None
    if not cutover_policy.is_cut_over(strategy_id):
        return None
    if not shadow_registry.is_registered(strategy_id):
        return None
    knowledge_or_unknown = (
        None
        if shadow_knowledge_by_subject is None
        else shadow_knowledge_by_subject.get(strategy_id)
    )
    if knowledge_or_unknown is None:
        knowledge_or_unknown = UnknownReason("subject_preparation_failed")
    binding = shadow_registry.binding_for(strategy_id)
    return _authoritative_subject_first_adapter(binding, knowledge_or_unknown, symbol)


def refresh_with_shadow(
    legacy_registry: StrategyRegistry[UniversalScreeningResult],
    repository: LatestResultRepository,
    clock: Clock,
    *,
    strategy_id: str,
    symbol: str,
    observations: Callable[[], tuple[MarketObservation, ...]],
    subject_first_observations: Callable[[], tuple[MarketObservation, ...]] = tuple,
    historical_skew_repository: HistoricalSkewRepository | None = None,
    shadow_registry: SubjectPreparationRegistry[object] | None = None,
    shadow_knowledge_by_subject: Mapping[str, ReadOnlyStrategyInput[object] | UnknownReason]
    | None = None,
    cutover_policy: CutoverPolicy | None = None,
    now: datetime | None = None,
) -> tuple[UniversalScreeningResult, ShadowParityDiagnostic | None]:
    """The one orchestration seam both production roots call, replacing a
    direct strategy_runtime.service.refresh() call.

    If ``cutover_policy`` is supplied and ``strategy_id`` is cut over
    (Architect checkpoint: nineteenth review, CUTOVER_PASS), and this
    subject's own already-prepared shadow knowledge for it is available,
    authoritative evaluation comes from that already-prepared knowledge
    instead of legacy -- legacy is never invoked, no shadow comparison
    runs (there is nothing left to compare against), and this function
    returns ``(result, None)``. This is the ONLY branch in this function
    keyed on ``cutover_policy``; every strategy_id absent from it (the
    default, empty policy) falls straight through to the unchanged
    behavior below.

    Otherwise, always runs and returns exactly what refresh() already
    would -- ``legacy_registry`` is expected to already be built with
    adapters closed over this subject's own PlanBackedFulfillment (built
    by build_subject_acquisition_access(), used identically to how a raw
    CapabilityFulfillmentService was closed over before), so legacy FF/
    Skew/Earnings execute unchanged through the same plan subject-first
    preparation already populated. ``observations`` itself is scoped down
    to ``strategy_id``'s own declared capabilities before being forwarded
    to refresh() (see _observations_relevant_to) so another strategy's own
    evidence sharing this same subject's plan this cycle -- including
    subject-first shadow preparation's own contribution -- never shifts
    this result's own temporal metadata.

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
    authoritative_adapter = _cutover_authoritative_adapter(
        cutover_policy, shadow_registry, shadow_knowledge_by_subject, strategy_id, symbol
    )
    if authoritative_adapter is not None:
        authoritative_registry: StrategyRegistry[UniversalScreeningResult] = StrategyRegistry(
            ((legacy_registry.contract_for(strategy_id), authoritative_adapter),)
        )
        result = refresh(
            authoritative_registry,
            repository,
            clock,
            strategy_id=strategy_id,
            symbol=symbol,
            observations=subject_first_observations,
            historical_skew_repository=None,
        )
        return result, None
    result = refresh(
        legacy_registry,
        repository,
        clock,
        strategy_id=strategy_id,
        symbol=symbol,
        observations=_observations_relevant_to(strategy_id, legacy_registry, observations),
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
