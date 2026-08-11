"""SPRINT-014 S14-PR-05A, Architect checkpoint item 4: the generic
planner must actually apply a CapabilityDemand's own declared temporal
policy (require_open_session/allow_prior_session/maximum_age_seconds),
producing typed RESOLVED/UNKNOWN evidence -- not hand a consumer's
expansion function raw, unvalidated evidence whose own demand identity
claimed a policy that was never actually applied.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from domain import (
    CapabilityDemand,
    CompletenessMetadata,
    EvidenceReference,
    EvidenceUsability,
    FreshnessMetadata,
    FreshnessStatus,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    ProviderProvenance,
    market_observation_identity,
)
from domain.market_data import MarketCapability, Quote
from domain.references import EvidenceKind
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    FulfillmentStatus,
    ProviderFulfillmentAttempt,
)
from market_data.providers import (
    CapabilityRequest,
    ProviderErrorCode,
    ProviderStatus,
    normalized_provider_error,
)
from screening.subject_planning import _project
from tests.domain.test_financial_contracts import security

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)


def _quote_demand(
    *,
    require_open_session: bool = False,
    allow_prior_session: bool = True,
    maximum_age_seconds: int | None = None,
) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.REAL_TIME_QUOTE_V1,
        ("last",),
        NOW,
        NOW,
        require_open_session=require_open_session,
        allow_prior_session=allow_prior_session,
        maximum_age_seconds=maximum_age_seconds,
    )


def _result_with_freshness(
    *,
    status: FreshnessStatus,
    age_seconds: int,
    threshold_seconds: int = 3600,
) -> CapabilityFulfillmentResult:
    subject = MarketDataSubject(
        security().instrument,
        MarketDataSubjectType.INSTRUMENT,
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketDataRequestContext(NOW, NOW, ("last",), (), EVIDENCE),
    )
    quote = Quote(security().instrument, None, None, Decimal("189.15"), None, None, None, "USD")
    effective_time = NOW - timedelta(seconds=age_seconds)
    observation_id = market_observation_identity(
        "tradier", MarketCapability.REAL_TIME_QUOTE_V1, subject, effective_time, quote, "v1"
    )
    observation = MarketObservation(
        observation_id,
        MarketCapability.REAL_TIME_QUOTE_V1,
        subject,
        effective_time,
        NOW,
        quote,
        "v1",
        ProviderProvenance("tradier", "tradier-request", EVIDENCE),
        FreshnessMetadata(NOW, effective_time, threshold_seconds, age_seconds, status),
        CompletenessMetadata(("last",), ("last",), ()),
    )
    attempt = ProviderFulfillmentAttempt(
        "tradier", 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    request = CapabilityRequest(
        MarketCapability.REAL_TIME_QUOTE_V1, (subject,), NOW, NOW, ("last",), 3600
    )
    return CapabilityFulfillmentResult(
        request, FulfillmentStatus.FULFILLED, "tradier", (observation,), (attempt,), True
    )


class TestTemporalUsabilityIsActuallyApplied:
    def test_fresh_evidence_within_market_hours_resolves(self) -> None:
        demand = _quote_demand(require_open_session=True)
        result = _result_with_freshness(status=FreshnessStatus.FRESH, age_seconds=0)

        projected = _project(demand.demand_id, demand, result, now=NOW, market_is_open=True)

        assert projected.usability is EvidenceUsability.RESOLVED
        assert projected.value is not None

    def test_closed_session_evidence_is_rejected_when_require_open_session_true(self) -> None:
        demand = _quote_demand(require_open_session=True)
        result = _result_with_freshness(status=FreshnessStatus.FRESH, age_seconds=0)

        projected = _project(demand.demand_id, demand, result, now=NOW, market_is_open=False)

        assert projected.usability is EvidenceUsability.UNKNOWN
        assert projected.value is None

    def test_closed_session_is_irrelevant_when_require_open_session_false(self) -> None:
        demand = _quote_demand(require_open_session=False)
        result = _result_with_freshness(status=FreshnessStatus.FRESH, age_seconds=0)

        projected = _project(demand.demand_id, demand, result, now=NOW, market_is_open=False)

        assert projected.usability is EvidenceUsability.RESOLVED

    def test_prior_session_evidence_resolves_when_allowed(self) -> None:
        demand = _quote_demand(allow_prior_session=True)
        result = _result_with_freshness(status=FreshnessStatus.PRIOR_SESSION, age_seconds=7200)

        projected = _project(demand.demand_id, demand, result, now=NOW, market_is_open=True)

        assert projected.usability is EvidenceUsability.RESOLVED
        assert projected.freshness_status is FreshnessStatus.PRIOR_SESSION

    def test_prior_session_evidence_is_rejected_when_disallowed(self) -> None:
        demand = _quote_demand(allow_prior_session=False)
        result = _result_with_freshness(status=FreshnessStatus.PRIOR_SESSION, age_seconds=7200)

        projected = _project(demand.demand_id, demand, result, now=NOW, market_is_open=True)

        assert projected.usability is EvidenceUsability.UNKNOWN

    def test_maximum_age_rejects_evidence_older_than_the_declared_policy(self) -> None:
        demand = _quote_demand(maximum_age_seconds=60)
        result = _result_with_freshness(status=FreshnessStatus.STALE, age_seconds=7200)

        projected = _project(demand.demand_id, demand, result, now=NOW, market_is_open=True)

        assert projected.usability is EvidenceUsability.UNKNOWN

    def test_maximum_age_accepts_evidence_within_the_declared_policy(self) -> None:
        demand = _quote_demand(maximum_age_seconds=3600)
        result = _result_with_freshness(status=FreshnessStatus.FRESH, age_seconds=30)

        projected = _project(demand.demand_id, demand, result, now=NOW, market_is_open=True)

        assert projected.usability is EvidenceUsability.RESOLVED

    def test_a_missing_result_is_typed_unknown_not_a_raised_exception(self) -> None:
        demand = _quote_demand()
        empty_request = CapabilityRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            _result_with_freshness(status=FreshnessStatus.FRESH, age_seconds=0).request.subjects,
            NOW,
            NOW,
            ("last",),
            3600,
        )
        # A FAILED result must still carry at least one real attempt per
        # CapabilityFulfillmentResult's own invariant.
        error = normalized_provider_error(
            ProviderErrorCode.NO_DATA, "no data", "tradier", MarketCapability.REAL_TIME_QUOTE_V1
        )
        failed = CapabilityFulfillmentResult(
            empty_request,
            FulfillmentStatus.FAILED,
            None,
            (),
            (ProviderFulfillmentAttempt("tradier", 1, ProviderStatus.AVAILABLE, (), error, ()),),
            True,
        )

        projected = _project(demand.demand_id, demand, failed, now=NOW, market_is_open=True)

        assert projected.usability is EvidenceUsability.UNKNOWN
        assert projected.value is None


class TestInputSkewHasNoUnenforcedIdentityBearingField:
    """SPRINT-014 S14-PR-05A, Architect checkpoint (second review):
    maximum_input_skew_seconds was removed from CapabilityDemand entirely
    -- it contributed to demand identity but had no real enforcement
    owner anywhere (market_data.temporal.evaluate_temporal_usability, the
    one function that would own it, never read it either). "Do not retain
    an identity-bearing policy field that has no behavioral effect."
    Multi-input-skew semantics (comparing effective times across more
    than one observation feeding one decision) has no real owner yet;
    it belongs alongside that owner when one exists, not before.
    """

    def test_capability_demand_has_no_input_skew_field(self) -> None:
        assert "maximum_input_skew_seconds" not in CapabilityDemand.__dataclass_fields__

    def test_subject_planning_never_names_input_skew(self) -> None:
        module = Path(__file__).resolve().parents[2] / "screening" / "subject_planning.py"
        assert "maximum_input_skew_seconds" not in module.read_text()
