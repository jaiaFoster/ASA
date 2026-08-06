"""SPRINT-014 S14-PR-05A, Architect checkpoint item 1: end-to-end proof
that capability coalescing and snapshot sealing actually compose
correctly -- the exact bug this checkpoint exists to fix (seal_subject_
snapshot reconstructing observations from raw per-attempt data instead of
a fulfillment result's own selected/coalesced observations, silently
discarding coalesce_option_chain_results' own combined observation and
reproducing PR #292's original multi-provider resolution conflict).
"""

from __future__ import annotations

from datetime import date

from domain import MarketCapability
from domain.financial import OptionChain
from market_data.capability_coalescing import coalesce_option_chain_results
from market_data.fulfillment import FulfillmentStatus
from market_data.providers import ProviderIdentity, ProviderMetadata
from market_data.resolution import ResolutionPolicy
from market_data.subject_snapshot import seal_subject_snapshot
from tests.market_data.test_capability_coalescing import (
    NOW,
    _failed_result,
    _request,
    _subject,
    _successful_result,
)

_PROVIDER_METADATA = (
    ProviderMetadata(
        ProviderIdentity("tradier", "test_provider", "v1"),
        (MarketCapability.OPTION_CHAIN_V1,),
        (),
        (MarketCapability.OPTION_CHAIN_V1,),
        "v1",
    ),
)
_RESOLUTION_POLICY = {
    MarketCapability.OPTION_CHAIN_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("contracts",))
}


class TestCoalescingIntoSealedSnapshot:
    def test_two_expiration_fulfillments_seal_into_one_resolved_result(self) -> None:
        front_result, front_obs = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result, back_obs = _successful_result("tradier", date(2026, 9, 18), suffix="back")

        coalesced = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )
        # Both raw source attempts genuinely survived coalescing -- proven
        # again here, at the integration boundary, not just at the unit
        # level (tests/market_data/test_capability_coalescing.py).
        assert len(coalesced.attempts) == 2

        snapshot = seal_subject_snapshot(
            (coalesced,),
            as_of=NOW,
            required_capabilities=(MarketCapability.OPTION_CHAIN_V1,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            provider_metadata=_PROVIDER_METADATA,
        )

        # Exactly one resolved OPTION_CHAIN_V1 result -- not the "one
        # value per provider" conflict raw front+back observations would
        # have produced (PR #292's own original failure mode).
        assert snapshot.completeness.resolved_capabilities == (MarketCapability.OPTION_CHAIN_V1,)
        assert snapshot.completeness.unresolved_capabilities == ()
        assert len(snapshot.observations) == 1

        sealed_chain = snapshot.observations[0].value
        assert isinstance(sealed_chain, OptionChain)
        assert len(sealed_chain.contracts) == 2  # one contract from each side, both present

        # The combined observation's own evidence -- not the snapshot's
        # top-level evidence -- is where both source observation ids are
        # referenced; this is the coalescer's own contract, reverified
        # here after a full seal rather than assumed.
        evidence_ids = {
            item.referenced_id for item in snapshot.observations[0].provenance.evidence
        }
        assert evidence_ids == {front_obs.observation_id, back_obs.observation_id}

    def test_one_success_one_failure_still_seals_the_successful_side(self) -> None:
        front_result, front_obs = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result = _failed_result("tradier", date(2026, 9, 18))

        coalesced = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )
        assert coalesced.status is FulfillmentStatus.DEGRADED
        assert len(coalesced.attempts) == 2  # the failed side's own attempt still present

        snapshot = seal_subject_snapshot(
            (coalesced,),
            as_of=NOW,
            required_capabilities=(MarketCapability.OPTION_CHAIN_V1,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            provider_metadata=_PROVIDER_METADATA,
        )

        assert snapshot.completeness.resolved_capabilities == (MarketCapability.OPTION_CHAIN_V1,)
        assert len(snapshot.observations) == 1
        sealed_chain = snapshot.observations[0].value
        assert isinstance(sealed_chain, OptionChain)
        assert len(sealed_chain.contracts) == 1  # only the successful side's contract
        evidence_ids = {
            item.referenced_id for item in snapshot.observations[0].provenance.evidence
        }
        assert evidence_ids == {front_obs.observation_id}

    def test_both_failures_seal_as_unresolved_not_silently_dropped(self) -> None:
        front_result = _failed_result("tradier", date(2026, 8, 21))
        back_result = _failed_result("tradier", date(2026, 9, 18))

        coalesced = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )
        assert coalesced.status is FulfillmentStatus.FAILED
        assert len(coalesced.attempts) == 2

        snapshot = seal_subject_snapshot(
            (coalesced,),
            as_of=NOW,
            required_capabilities=(MarketCapability.OPTION_CHAIN_V1,),
            resolution_policy_by_capability=_RESOLUTION_POLICY,
            provider_metadata=_PROVIDER_METADATA,
        )

        assert snapshot.completeness.resolved_capabilities == ()
        assert snapshot.completeness.unresolved_capabilities == (MarketCapability.OPTION_CHAIN_V1,)
        assert snapshot.observations == ()
