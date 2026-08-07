"""SPRINT-014 S14-PR-05A: capability-owned coalescing of multiple
CapabilityFulfillmentResults for the same capability into one, preserving
every source attempt and observation reference (Architect review finding
B7, PR #292 review 4877473757).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime

import pytest

from domain import (
    CompletenessMetadata,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
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
from domain.values import DomainInvariantError
from market_data.capability_coalescing import (
    coalesce_option_chain_results,
    combine_option_chains,
    reduce_option_chain_results,
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


def _expirations_subject() -> MarketDataSubject:
    projection = ProviderAddressProjection("tradier", "v1", "symbol", "AAPL", NOW, None, EVIDENCE)
    return MarketDataSubject(
        security().instrument,
        MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.OPTION_CHAIN_V1,
        MarketDataRequestContext(NOW, NOW, ("expirations",), (projection,), EVIDENCE),
    )


def _expirations_request() -> CapabilityRequest:
    return CapabilityRequest(
        MarketCapability.OPTION_CHAIN_V1,
        (_expirations_subject(),),
        NOW,
        NOW,
        ("expirations",),
        3600,
    )


def _expirations_observation(
    provider_id: str, expirations: tuple[date, ...]
) -> MarketObservation:
    as_of = NOW.date()
    cycles = tuple(
        ExpirationCycle(item, (item - as_of).days, True, False, as_of, EVIDENCE)
        for item in expirations
    )
    value = ExpirationCollection(as_of, cycles)
    subject = _expirations_subject()
    provenance = ProviderProvenance(provider_id, f"{provider_id}-request-expirations", EVIDENCE)
    identity = market_observation_identity(
        provider_id, MarketCapability.OPTION_CHAIN_V1, subject, NOW, value, "v1"
    )
    return MarketObservation(
        identity,
        MarketCapability.OPTION_CHAIN_V1,
        subject,
        NOW,
        NOW,
        value,
        "v1",
        provenance,
        FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(("expirations",), ("expirations",), ()),
    )


def _expirations_result(
    provider_id: str, expirations: tuple[date, ...]
) -> CapabilityFulfillmentResult:
    observation = _expirations_observation(provider_id, expirations)
    attempt = ProviderFulfillmentAttempt(
        provider_id, 1, ProviderStatus.AVAILABLE, (observation,), None, ()
    )
    return CapabilityFulfillmentResult(
        _expirations_request(),
        FulfillmentStatus.FULFILLED,
        provider_id,
        (observation,),
        (attempt,),
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

    def test_status_reflects_result_level_success_not_an_observation_count_comparison(
        self,
    ) -> None:
        """A single CapabilityFulfillmentResult can legitimately carry more
        than one observation (e.g. a DEGRADED multi-provider resolution
        upstream feeding into this coalescer) -- comparing
        len(observations) to len(results) would misclassify one fully
        successful result carrying two observations as partial failure.
        """
        front = _chain_observation("tradier", date(2026, 8, 21), suffix="front")
        back = _chain_observation("tradier", date(2026, 9, 18), suffix="back")
        one_result_two_observations = CapabilityFulfillmentResult(
            _request(),
            FulfillmentStatus.FULFILLED,
            "tradier",
            (front, back),
            (_successful_attempt("tradier", front), _successful_attempt("tradier", back)),
            True,
        )

        combined = coalesce_option_chain_results(
            (one_result_two_observations,),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )

        assert combined.status is FulfillmentStatus.FULFILLED

    def test_a_non_option_chain_value_on_a_successful_observation_raises_not_silently_dropped(
        self,
    ) -> None:
        """OPTION_CHAIN_V1 is a capability tag several distinct domain
        value types can legitimately carry (OptionChain, OptionContract,
        ExpirationCycle -- domain/market_data.py's own expected_capability
        mapping) -- an ExpirationCycle observation (the shape
        acquire_expirations() itself resolves under this same capability)
        reaching this coalescer is a real, reachable upstream-wiring
        defect, not a hypothetical one. It must raise, never be silently
        filtered out of the combined chain.
        """
        front_result, _ = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        expiration_cycle = ExpirationCycle(
            date(2026, 9, 18), 43, True, False, NOW.date(), EVIDENCE
        )
        provenance = ProviderProvenance("tradier", "tradier-request-wrong-shape", EVIDENCE)
        freshness = FreshnessMetadata(NOW, NOW, 3600, 0, FreshnessStatus.FRESH)
        completeness = CompletenessMetadata(("contracts",), ("contracts",), ())
        wrong_value_observation = MarketObservation(
            market_observation_identity(
                "tradier", MarketCapability.OPTION_CHAIN_V1, _subject(), NOW, expiration_cycle, "v1"
            ),
            MarketCapability.OPTION_CHAIN_V1,
            _subject(),
            NOW,
            NOW,
            expiration_cycle,
            "v1",
            provenance,
            freshness,
            completeness,
        )
        malformed_result = CapabilityFulfillmentResult(
            _request(expiration=date(2026, 9, 18)),
            FulfillmentStatus.FULFILLED,
            "tradier",
            (wrong_value_observation,),
            (_successful_attempt("tradier", wrong_value_observation),),
            True,
        )

        with pytest.raises(DomainInvariantError):
            coalesce_option_chain_results(
                (front_result, malformed_result),
                subject=_subject(),
                combined_request=_request(),
                observed_at=NOW,
            )


class TestReduceOptionChainResults:
    """SPRINT-014 S14-PR-05A, Architect checkpoint (fourth review): the
    bounded reducer that lets a subject's own mixed OPTION_CHAIN_V1
    demands -- expiration discovery (("expirations",) -> ExpirationCollection)
    plus per-expiration contract acquisition (("contracts",) -> OptionChain)
    -- seal together through the generic planner's own capability
    reduction step, which the unmodified coalesce_option_chain_results()
    alone cannot do (it raises DomainInvariantError on a non-OptionChain
    successful observation).
    """

    def test_requires_at_least_one_result(self) -> None:
        with pytest.raises(ValueError):
            reduce_option_chain_results(())

    def test_lone_expiration_discovery_result_seals_unchanged(self) -> None:
        discovery = _expirations_result("tradier", (date(2026, 8, 21), date(2026, 9, 18)))
        reduced = reduce_option_chain_results((discovery,))
        assert reduced is discovery

    def test_mixed_discovery_and_contract_results_combine_the_chains_only(self) -> None:
        discovery = _expirations_result("tradier", (date(2026, 8, 21), date(2026, 9, 18)))
        front_result, _ = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result, _ = _successful_result("tradier", date(2026, 9, 18), suffix="back")

        reduced = reduce_option_chain_results((discovery, front_result, back_result))

        assert reduced.status is FulfillmentStatus.FULFILLED
        assert len(reduced.observations) == 1
        combined_chain = reduced.observations[0].value
        assert isinstance(combined_chain, OptionChain)
        assert len(combined_chain.contracts) == 2
        # Every raw attempt, including discovery's own, survives -- so
        # MarketSnapshotBuilder's own union of observations/attempts still
        # retains the ExpirationCollection downstream.
        assert len(reduced.attempts) == 3
        discovery_observation_ids = {
            observation.observation_id
            for attempt in reduced.attempts
            for observation in attempt.observations
            if isinstance(observation.value, ExpirationCollection)
        }
        assert discovery_observation_ids == {discovery.observations[0].observation_id}
        # The combined chain is the selected/coalesced observation, never
        # the discovery evidence.
        assert not isinstance(reduced.observations[0].value, ExpirationCollection)

    def test_a_failed_contract_side_still_combines_with_discovery_preserved(self) -> None:
        discovery = _expirations_result("tradier", (date(2026, 8, 21), date(2026, 9, 18)))
        front_result, _ = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result = _failed_result("tradier", date(2026, 9, 18))

        reduced = reduce_option_chain_results((discovery, front_result, back_result))

        assert reduced.status is FulfillmentStatus.DEGRADED
        assert len(reduced.attempts) == 3
        combined_chain = reduced.observations[0].value
        assert isinstance(combined_chain, OptionChain)
        assert len(combined_chain.contracts) == 1

    def test_only_option_chain_capability_is_accepted(self) -> None:
        quote_subject = MarketDataSubject(
            security().instrument,
            MarketDataSubjectType.INSTRUMENT,
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketDataRequestContext(NOW, NOW, ("last",), (), EVIDENCE),
        )
        wrong_capability_request = CapabilityRequest(
            MarketCapability.REAL_TIME_QUOTE_V1, (quote_subject,), NOW, NOW, ("last",), 3600
        )
        wrong_capability_result = CapabilityFulfillmentResult(
            wrong_capability_request,
            FulfillmentStatus.FAILED,
            None,
            (),
            (_failed_attempt("tradier"),),
            True,
        )
        with pytest.raises(ValueError):
            reduce_option_chain_results((wrong_capability_result,))

    def test_unexpected_required_fields_raises(self) -> None:
        weird_subject = MarketDataSubject(
            security().instrument,
            MarketDataSubjectType.OPTION_UNDERLYING,
            MarketCapability.OPTION_CHAIN_V1,
            MarketDataRequestContext(NOW, NOW, ("greeks",), (), EVIDENCE),
        )
        weird_request = CapabilityRequest(
            MarketCapability.OPTION_CHAIN_V1, (weird_subject,), NOW, NOW, ("greeks",), 3600
        )
        weird_result = CapabilityFulfillmentResult(
            weird_request, FulfillmentStatus.FAILED, None, (), (_failed_attempt("tradier"),), True
        )
        with pytest.raises(DomainInvariantError, match="unexpected required_fields"):
            reduce_option_chain_results((weird_result,))

    def test_a_non_expiration_collection_value_on_a_nominal_discovery_result_raises(self) -> None:
        """A nominally successful ("expirations",) result whose own
        observation carries something other than ExpirationCollection is a
        real, reachable upstream-wiring defect (an EXPECTED_FIELDS/value
        mismatch), never silently accepted.
        """
        front_result, _ = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        mislabeled_as_discovery = dataclasses.replace(
            front_result, request=_expirations_request()
        )
        with pytest.raises(DomainInvariantError, match="not ExpirationCollection"):
            reduce_option_chain_results((mislabeled_as_discovery,))

    def test_no_contract_results_and_multiple_discovery_results_raises(self) -> None:
        first = _expirations_result("tradier", (date(2026, 8, 21),))
        second = _expirations_result("finnhub", (date(2026, 8, 21),))
        with pytest.raises(DomainInvariantError, match="no reduction is defined"):
            reduce_option_chain_results((first, second))
