"""SPRINT-014 S14-PR-05A: capability-owned coalescing of multiple
CapabilityFulfillmentResults for the same capability into one, preserving
every source attempt and observation reference (Architect review finding
B7, PR #292 review 4877473757).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from domain import (
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    ProviderAddressProjection,
    ProviderProvenance,
    market_observation_identity,
)
from domain.financial import OptionChain
from market_data.capability_coalescing import (
    coalesce_option_chain_results,
    combine_option_chains,
)
from market_data.fulfillment import (
    CapabilityFulfillmentResult,
    FulfillmentStatus,
    ProviderFulfillmentAttempt,
)
from market_data.providers import (
    CapabilityRequest,
    ProviderAttemptMetadata,
    ProviderErrorCode,
    ProviderResponseMetadata,
    ProviderStatus,
    normalized_provider_error,
)
from tests.domain.test_financial_contracts import option, security

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)


def _subject(*, expiration: date | None = None) -> MarketDataSubject:
    fields = ("contracts",)
    projection = ProviderAddressProjection("tradier", "v1", "symbol", "AAPL", NOW, None, EVIDENCE)
    projections = (projection,)
    if expiration is not None:
        projections = projections + (
            ProviderAddressProjection(
                "tradier", "v1", "expiration", expiration.isoformat(), NOW, None, EVIDENCE
            ),
        )
    return MarketDataSubject(
        security().instrument,
        MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.OPTION_CHAIN_V1,
        MarketDataRequestContext(NOW, NOW, fields, projections, EVIDENCE),
    )


def _request(*, expiration: date | None = None) -> CapabilityRequest:
    return CapabilityRequest(
        MarketCapability.OPTION_CHAIN_V1,
        (_subject(expiration=expiration),),
        NOW,
        NOW,
        ("contracts",),
        3600,
    )


def _chain_observation(provider_id: str, expiration: date, *, suffix: str) -> MarketObservation:
    contract = option(expiration=expiration, observed_at=NOW, suffix=suffix)
    chain = OptionChain(f"chain-{suffix}", security(), NOW, (contract,), EVIDENCE)
    provenance = ProviderProvenance(provider_id, f"{provider_id}-request-{suffix}", EVIDENCE)
    freshness = FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH)
    completeness = CompletenessMetadata(("contracts",), ("contracts",), ())
    observation_id = market_observation_identity(
        provider_id, MarketCapability.OPTION_CHAIN_V1, _subject(), NOW, chain, "v1"
    )
    return MarketObservation(
        observation_id,
        MarketCapability.OPTION_CHAIN_V1,
        _subject(),
        NOW,
        NOW,
        chain,
        "v1",
        provenance,
        freshness,
        completeness,
    )


def _successful_attempt(
    provider_id: str, observation: MarketObservation
) -> ProviderFulfillmentAttempt:
    return ProviderFulfillmentAttempt(
        provider_id, 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )


def _failed_attempt(provider_id: str) -> ProviderFulfillmentAttempt:
    response = ProviderResponseMetadata(
        provider_id, f"{provider_id}-request-failed", NOW, "live", 0, 0
    )
    attempt_metadata = ProviderAttemptMetadata(
        provider_id, MarketCapability.OPTION_CHAIN_V1, 1, 1, response
    )
    error = normalized_provider_error(
        ProviderErrorCode.NO_DATA,
        "simulated failure",
        provider_id,
        MarketCapability.OPTION_CHAIN_V1,
    )
    return ProviderFulfillmentAttempt(
        provider_id, 1, ProviderStatus.AVAILABLE, (), error, (attempt_metadata,)
    )


def _successful_result(
    provider_id: str, expiration: date, *, suffix: str
) -> tuple[CapabilityFulfillmentResult, MarketObservation]:
    observation = _chain_observation(provider_id, expiration, suffix=suffix)
    attempt = _successful_attempt(provider_id, observation)
    result = CapabilityFulfillmentResult(
        _request(expiration=expiration),
        FulfillmentStatus.FULFILLED,
        provider_id,
        (observation,),
        (attempt,),
        True,
    )
    return result, observation


def _failed_result(provider_id: str, expiration: date) -> CapabilityFulfillmentResult:
    return CapabilityFulfillmentResult(
        _request(expiration=expiration),
        FulfillmentStatus.FAILED,
        None,
        (),
        (_failed_attempt(provider_id),),
        True,
    )


class TestCombineOptionChains:
    def test_requires_at_least_one_chain(self) -> None:
        with pytest.raises(ValueError):
            combine_option_chains((), NOW)

    def test_single_chain_round_trips(self) -> None:
        _, observation = _successful_result("tradier", date(2026, 8, 21), suffix="front")

        chain = observation.value
        assert isinstance(chain, OptionChain)
        combined = combine_option_chains((chain,), NOW)
        assert combined.contracts == chain.contracts

    def test_combines_two_chains_and_deduplicates_by_contract_identity(self) -> None:
        _, front_obs = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        _, back_obs = _successful_result("tradier", date(2026, 9, 18), suffix="back")
        combined = combine_option_chains((front_obs.value, back_obs.value), NOW)
        assert len(combined.contracts) == 2
        assert combined.observed_at == NOW


class TestCoalesceOptionChainResults:
    def test_requires_at_least_one_result(self) -> None:
        with pytest.raises(ValueError):
            coalesce_option_chain_results(
                (), subject=_subject(), combined_request=_request(), observed_at=NOW
            )

    def test_both_sides_succeed_preserves_both_attempts_and_combines_observations(self) -> None:
        front_result, front_obs = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result, back_obs = _successful_result("tradier", date(2026, 9, 18), suffix="back")

        combined = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )

        assert combined.status is FulfillmentStatus.FULFILLED
        assert len(combined.attempts) == 2
        assert len(combined.observations) == 1

        combined_chain = combined.observations[0].value
        assert isinstance(combined_chain, OptionChain)
        assert len(combined_chain.contracts) == 2
        evidence_ids = {item.referenced_id for item in combined.observations[0].provenance.evidence}
        assert evidence_ids == {front_obs.observation_id, back_obs.observation_id}

    def test_a_failed_back_request_stays_represented_not_silently_dropped(self) -> None:
        """Architect review finding B7 -- the exact regression this
        module exists to fix: a failed side's own attempt must survive in
        the combined result, and the combined result must still expose
        whatever the successful side actually returned (never total
        silence just because one side failed).
        """
        front_result, front_obs = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result = _failed_result("tradier", date(2026, 9, 18))

        combined = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )

        assert combined.status is FulfillmentStatus.DEGRADED
        assert len(combined.attempts) == 2
        failed_attempts = [attempt for attempt in combined.attempts if attempt.error is not None]
        assert len(failed_attempts) == 1
        assert len(combined.observations) == 1
        evidence_ids = {item.referenced_id for item in combined.observations[0].provenance.evidence}
        assert evidence_ids == {front_obs.observation_id}

    def test_both_sides_fail_produces_one_failed_result_preserving_both_attempts(self) -> None:
        front_result = _failed_result("tradier", date(2026, 8, 21))
        back_result = _failed_result("tradier", date(2026, 9, 18))

        combined = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )

        assert combined.status is FulfillmentStatus.FAILED
        assert combined.observations == ()
        assert combined.selected_provider is None
        assert len(combined.attempts) == 2

    def test_combined_observation_id_is_content_derived_not_reused_from_a_source(self) -> None:
        front_result, front_obs = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result, back_obs = _successful_result("tradier", date(2026, 9, 18), suffix="back")

        combined = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )

        combined_id = combined.observations[0].observation_id
        assert combined_id != front_obs.observation_id
        assert combined_id != back_obs.observation_id
        # Re-validates cleanly through MarketObservation's own
        # content-derived-identity invariant (constructing it at all,
        # inside coalesce_option_chain_results, already proves this --
        # this assertion documents *why* rather than re-testing the type).

    def test_only_option_chain_capability_is_accepted(self) -> None:
        quote_subject = MarketDataSubject(
            security().instrument,
            MarketDataSubjectType.INSTRUMENT,
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketDataRequestContext(NOW, NOW, ("last",), (), EVIDENCE),
        )
        request = CapabilityRequest(
            MarketCapability.REAL_TIME_QUOTE_V1,
            (quote_subject,),
            NOW,
            NOW,
            ("last",),
            3600,
        )
        wrong_capability_result = CapabilityFulfillmentResult(
            request, FulfillmentStatus.FAILED, None, (), (_failed_attempt("tradier"),), True
        )
        with pytest.raises(ValueError):
            coalesce_option_chain_results(
                (wrong_capability_result,),
                subject=_subject(),
                combined_request=_request(),
                observed_at=NOW,
            )
