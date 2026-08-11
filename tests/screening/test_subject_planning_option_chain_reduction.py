"""SPRINT-014 S14-PR-05A, Architect checkpoint (fourth review): the first
real Earnings-shaped execution path exposed a blocker the synthetic,
ResolvedCapabilityEvidence-only tests in test_subject_planning.py could
not reach -- Earnings legitimately produces three OPTION_CHAIN_V1 demands
per subject (one expiration-discovery request plus two per-expiration
contract requests), and the generic planner's own capability-reduction
step required a dedicated reducer that understands both request shapes.

market_data.capability_coalescing.reduce_option_chain_results is that
reducer. This module proves it end-to-end through the real
run_subject_plan() -> capability reduction -> seal_subject_snapshot path,
using a synthetic, Earnings-*shaped* consumer -- never an import of
strategies.earnings_calendar_planning or any real strategy branch, per
the Architect's own explicit instruction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from domain import (
    CapabilityDemand,
    CompletenessMetadata,
    DemandExpansion,
    EvidenceKind,
    EvidenceReference,
    EvidenceUsability,
    ExpirationCollection,
    ExpirationCycle,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataSubject,
    MarketObservation,
    ProviderProvenance,
    ResolvedCapabilityEvidence,
    market_observation_identity,
)
from domain.financial import OptionChain
from market_data import (
    BudgetScope,
    CapabilityFulfillmentService,
    CapabilityRegistry,
    CapabilityRequest,
    HealthProbe,
    ProviderAttemptMetadata,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderHealthReport,
    ProviderIdentity,
    ProviderMetadata,
    ProviderPriority,
    ProviderPriorityPolicy,
    ProviderRegistry,
    ProviderResponseMetadata,
    ProviderShutdownReport,
    ProviderStatus,
    ProviderValidationPlan,
    ProviderValidationReport,
    RequestBudgetAuthorization,
    RequestBudgetManager,
    RequestBudgetPolicy,
    normalized_provider_error,
)
from market_data.attempts import InMemoryAcquisitionAttemptRepository
from market_data.capability_coalescing import reduce_option_chain_results
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import SubjectAcquisitionPlan
from screening.subject_planning import SubjectPlanConsumer, run_subject_plan
from tests.domain.test_financial_contracts import option, security
from tests.market_data.test_fulfillment import Clock

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
FRONT_EXPIRATION = date(2026, 8, 21)
BACK_EXPIRATION = date(2026, 9, 18)
CAPABILITY = MarketCapability.OPTION_CHAIN_V1
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)
_RESOLUTION_POLICY = {CAPABILITY: ResolutionPolicy("v1", ("tradier",), 3600, ("contracts",))}
# A resolution policy's own required_fields describes the minimum shape
# its capability's *final sealed* value must provide -- for the "no
# valid expiration pair" outcome, that is the lone ExpirationCollection
# discovery result itself, never the ("contracts",) shape only a
# combined chain (never produced in that outcome) would satisfy.
_DISCOVERY_ONLY_RESOLUTION_POLICY = {
    CAPABILITY: ResolutionPolicy("v1", ("tradier",), 3600, ("expirations",))
}


def _expiration_cycle(expiration_date: date) -> ExpirationCycle:
    as_of = NOW.date()
    return ExpirationCycle(
        expiration_date, (expiration_date - as_of).days, True, False, as_of, EVIDENCE
    )


def _chain(expiration_date: date) -> OptionChain:
    underlying = security()
    contract = option(
        expiration=expiration_date,
        observed_at=NOW,
        underlying=underlying,
        suffix=expiration_date.isoformat(),
    )
    chain_id = f"chain-{expiration_date.isoformat()}"
    return OptionChain(chain_id, underlying, NOW, (contract,), EVIDENCE)


def _observation(
    provider_id: str,
    subject: MarketDataSubject,
    value: ExpirationCollection | OptionChain,
    request_reference: str,
) -> MarketObservation:
    provenance = ProviderProvenance(provider_id, request_reference, EVIDENCE)
    identity = market_observation_identity(provider_id, CAPABILITY, subject, NOW, value, "v1")
    fields = subject.request_context.required_fields
    return MarketObservation(
        identity,
        CAPABILITY,
        subject,
        NOW,
        NOW,
        value,
        "v1",
        provenance,
        FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(fields, fields, ()),
    )


@dataclass
class _EarningsShapedProvider:
    """A minimal Provider-Protocol implementation producing exactly the
    three OPTION_CHAIN_V1 response shapes an Earnings-shaped subject plan
    issues: expiration discovery, and one chain per selected expiration.
    Built the same way test_fulfillment.py's own ScriptedProvider is,
    generalized to more than one required_fields shape -- never a real
    strategy import.
    """

    provider_id: str
    fail_back: bool = False
    call_log: list[CapabilityRequest] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.metadata = ProviderMetadata(
            ProviderIdentity(self.provider_id, "test_provider", "v1"),
            (CAPABILITY,),
            (),
            (CAPABILITY,),
            "v1",
        )

    @property
    def capabilities(self) -> tuple[MarketCapability, ...]:
        return self.metadata.capabilities

    def fetch(
        self, request: CapabilityRequest, budget: RequestBudgetAuthorization
    ) -> ProviderFetchResult:
        self.call_log.append(request)
        response = ProviderResponseMetadata(
            self.provider_id, f"{self.provider_id}-req-{len(self.call_log)}", NOW, "fixture", 0, 0
        )
        attempt = ProviderAttemptMetadata(self.provider_id, CAPABILITY, 1, 1, response)
        subject = request.subjects[0]
        if request.required_fields == ("expirations",):
            collection = ExpirationCollection(
                NOW.date(),
                (_expiration_cycle(FRONT_EXPIRATION), _expiration_cycle(BACK_EXPIRATION)),
            )
            observation = _observation(
                self.provider_id, subject, collection, response.provider_request_reference
            )
            return ProviderFetchResult((observation,), None, (attempt,))
        expiration = date.fromisoformat(
            subject.projection_for(self.provider_id, "expiration", NOW).address_value
        )
        if expiration == BACK_EXPIRATION and self.fail_back:
            error = normalized_provider_error(
                ProviderErrorCode.NO_DATA, "simulated failure", self.provider_id, CAPABILITY
            )
            return ProviderFetchResult((), error, (attempt,))
        chain = _chain(expiration)
        observation = _observation(
            self.provider_id, subject, chain, response.provider_request_reference
        )
        return ProviderFetchResult((observation,), None, (attempt,))

    def health(self, probe: HealthProbe) -> ProviderHealthReport:
        return ProviderHealthReport(self.provider_id, ProviderStatus.AVAILABLE, NOW, "OK", None)

    def validate(self, plan: ProviderValidationPlan) -> ProviderValidationReport:
        raise NotImplementedError

    def shutdown(self) -> ProviderShutdownReport:
        return ProviderShutdownReport(self.provider_id, NOW)


def _service(provider: _EarningsShapedProvider) -> CapabilityFulfillmentService:
    registry = ProviderRegistry((provider,))
    capabilities = CapabilityRegistry(
        registry, ProviderPriorityPolicy("v1", (ProviderPriority(CAPABILITY, ("tradier",)),))
    )
    budgets = RequestBudgetManager(
        (RequestBudgetPolicy("tradier", BudgetScope.RUNTIME, 10, 10, 0, "v1"),), Clock()
    )
    return CapabilityFulfillmentService(registry, capabilities, budgets)


def _plan(fulfillment: CapabilityFulfillmentService) -> SubjectAcquisitionPlan:
    return SubjectAcquisitionPlan(
        "AAPL",
        fulfillment,
        attempt_repository=InMemoryAcquisitionAttemptRepository(),
        plan_id="cycle-1:AAPL",
        clock=Clock(NOW),
    )


def _expirations_demand() -> CapabilityDemand:
    return CapabilityDemand(CAPABILITY, ("expirations",), NOW, NOW)


def _chain_demand(expiration_date: date) -> CapabilityDemand:
    return CapabilityDemand(CAPABILITY, ("contracts",), NOW, NOW, expiration=expiration_date)


def _expand_to_front_and_back(
    evidence: Mapping[str, ResolvedCapabilityEvidence],
) -> DemandExpansion:
    """The Earnings-shaped phase-two expansion this test proves against:
    given phase-one's own expiration-discovery evidence, always selects
    the fixed FRONT/BACK_EXPIRATION pair -- deliberately not the real
    strategies.earnings_calendar_planning selection logic, which has its
    own dedicated test coverage; this module only proves the generic
    planner's own capability-reduction integration.
    """
    demand_evidence = evidence[_expirations_demand().demand_id]
    assert demand_evidence.usability is EvidenceUsability.RESOLVED
    assert isinstance(demand_evidence.value, ExpirationCollection)
    front_demand = _chain_demand(FRONT_EXPIRATION)
    back_demand = _chain_demand(BACK_EXPIRATION)
    return DemandExpansion(
        demands=(front_demand, back_demand),
        selections=(
            ("front_demand_id", front_demand.demand_id),
            ("back_demand_id", back_demand.demand_id),
        ),
    )


def _no_phase_two(_evidence: Mapping[str, ResolvedCapabilityEvidence]) -> DemandExpansion:
    return DemandExpansion()


def _consumer(
    expand: Callable[
        [Mapping[str, ResolvedCapabilityEvidence]], DemandExpansion
    ] = _expand_to_front_and_back,
) -> SubjectPlanConsumer:
    return SubjectPlanConsumer("earnings", (_expirations_demand(),), expand)


def _provider_metadata(provider: _EarningsShapedProvider) -> tuple[ProviderMetadata, ...]:
    return (provider.metadata,)


class TestEarningsShapedOptionChainReduction:
    def test_plan_seals_with_one_final_resolution_selecting_the_combined_chain(self) -> None:
        provider = _EarningsShapedProvider("tradier")
        fulfillment = _service(provider)
        plan = _plan(fulfillment)

        result = run_subject_plan(
            plan,
            NOW,
            (_consumer(),),
            provider_metadata=_provider_metadata(provider),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            capability_reducer_by_capability={CAPABILITY: reduce_option_chain_results},
        )

        assert len(result.snapshot.resolution_results) == 1
        resolution = result.snapshot.resolution_results[0]
        assert resolution.capability is CAPABILITY
        assert resolution.selected_observation is not None
        combined = resolution.selected_observation.value
        assert isinstance(combined, OptionChain)
        assert len(combined.contracts) == 2

        observation_ids = {item.observation_id for item in result.snapshot.observations}
        expiration_collection_ids = {
            item.observation_id
            for item in result.snapshot.observations
            if isinstance(item.value, ExpirationCollection)
        }
        chain_ids = {
            item.observation_id
            for item in result.snapshot.observations
            if isinstance(item.value, OptionChain)
        }
        assert len(expiration_collection_ids) == 1
        # Both raw source chains plus the combined chain: three OptionChain
        # observations total.
        assert len(chain_ids) == 3
        combined_evidence_ids = {
            item.referenced_id for item in resolution.selected_observation.provenance.evidence
        }
        assert combined_evidence_ids == chain_ids - {resolution.selected_observation.observation_id}
        assert observation_ids == expiration_collection_ids | chain_ids

        expansion = result.expansions_by_consumer["earnings"]
        selections = dict(expansion.selections)
        front_id = selections["front_demand_id"]
        back_id = selections["back_demand_id"]
        expirations_id = _expirations_demand().demand_id
        assert {expirations_id, front_id, back_id} <= set(result.projected_evidence)
        assert len({expirations_id, front_id, back_id}) == 3

        assert len(provider.call_log) == 3

        again = run_subject_plan(
            plan,
            NOW,
            (_consumer(),),
            provider_metadata=_provider_metadata(provider),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            capability_reducer_by_capability={CAPABILITY: reduce_option_chain_results},
        )
        assert again.snapshot.observations == result.snapshot.observations
        assert len(provider.call_log) == 3

    def test_a_failed_back_side_stays_typed_unknown_without_losing_discovery_evidence(
        self,
    ) -> None:
        provider = _EarningsShapedProvider("tradier", fail_back=True)
        fulfillment = _service(provider)
        plan = _plan(fulfillment)

        result = run_subject_plan(
            plan,
            NOW,
            (_consumer(),),
            provider_metadata=_provider_metadata(provider),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            capability_reducer_by_capability={CAPABILITY: reduce_option_chain_results},
        )

        expansion = result.expansions_by_consumer["earnings"]
        selections = dict(expansion.selections)
        back_id = selections["back_demand_id"]
        assert isinstance(back_id, str)
        expirations_id = _expirations_demand().demand_id

        assert result.projected_evidence[back_id].usability is EvidenceUsability.UNKNOWN
        assert result.projected_evidence[expirations_id].usability is EvidenceUsability.RESOLVED
        assert isinstance(result.projected_evidence[expirations_id].value, ExpirationCollection)

        expiration_collection_ids = {
            item.observation_id
            for item in result.snapshot.observations
            if isinstance(item.value, ExpirationCollection)
        }
        assert len(expiration_collection_ids) == 1

        assert len(result.snapshot.resolution_results) == 1
        resolution = result.snapshot.resolution_results[0]
        assert resolution.selected_observation is not None
        combined = resolution.selected_observation.value
        assert isinstance(combined, OptionChain)
        # Only the front side's own single contract -- the failed back
        # side contributes nothing to the combined chain.
        assert len(combined.contracts) == 1

    def test_no_phase_two_chains_seals_the_lone_expiration_collection(self) -> None:
        provider = _EarningsShapedProvider("tradier")
        fulfillment = _service(provider)
        plan = _plan(fulfillment)

        result = run_subject_plan(
            plan,
            NOW,
            (_consumer(_no_phase_two),),
            provider_metadata=_provider_metadata(provider),
            resolution_policy_by_capability=_DISCOVERY_ONLY_RESOLUTION_POLICY,
            capability_reducer_by_capability={CAPABILITY: reduce_option_chain_results},
        )

        assert result.snapshot.completeness.resolved_capabilities == (CAPABILITY,)
        assert len(result.snapshot.observations) == 1
        assert isinstance(result.snapshot.observations[0].value, ExpirationCollection)
        assert len(result.snapshot.resolution_results) == 1
        resolution = result.snapshot.resolution_results[0]
        assert resolution.selected_observation is not None
        assert isinstance(resolution.selected_observation.value, ExpirationCollection)
        assert len(provider.call_log) == 1
