"""SPRINT-014 S14-PR-05A, Architect checkpoint item 1/2: end-to-end proof
that capability coalescing and snapshot sealing actually compose
correctly and produce a self-contained sealed snapshot -- the exact bugs
this checkpoint exists to fix:

* seal_subject_snapshot() (market_data/subject_snapshot.py) reconstructing
  its resolver input from raw per-attempt data instead of a fulfillment
  result's own selected/coalesced observations, silently discarding
  coalesce_option_chain_results' own combined observation and reproducing
  PR #292's original multi-provider resolution conflict (first review,
  fixed).
* MarketSnapshotBuilder.build() (market_data/snapshot.py) storing only
  the fulfillment's own selected/coalesced observations on the sealed
  snapshot, leaving the combined observation's own referenced source
  observation ids -- and, when front and back are served by different
  providers, that second provider's own metadata -- absent from the
  snapshot itself (second review, fixed here: the snapshot's own
  ``observations`` is now the union of selected/coalesced and every raw
  per-attempt observation).
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


def _provider_metadata(provider_id: str) -> ProviderMetadata:
    return ProviderMetadata(
        ProviderIdentity(provider_id, "test_provider", "v1"),
        (MarketCapability.OPTION_CHAIN_V1,),
        (),
        (MarketCapability.OPTION_CHAIN_V1,),
        "v1",
    )


_PROVIDER_METADATA = (_provider_metadata("tradier"),)
_RESOLUTION_POLICY = {
    MarketCapability.OPTION_CHAIN_V1: ResolutionPolicy("v1", ("tradier",), 3600, ("contracts",))
}


def _combined_observation(snapshot, exclude_ids: set[str]):
    (combined,) = [
        item for item in snapshot.observations if item.observation_id not in exclude_ids
    ]
    return combined


class TestCoalescingIntoSealedSnapshot:
    def test_two_expiration_fulfillments_seal_self_contained_provenance(self) -> None:
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

        # Exactly one *resolved* OPTION_CHAIN_V1 value -- not the "one
        # value per provider" conflict raw front+back observations would
        # have produced (PR #292's own original failure mode) -- but the
        # sealed snapshot is now self-contained: both raw sources plus the
        # combined observation all survive as real, independently
        # addressable observations.
        assert snapshot.completeness.resolved_capabilities == (MarketCapability.OPTION_CHAIN_V1,)
        assert snapshot.completeness.unresolved_capabilities == ()
        assert len(snapshot.observations) == 3

        observation_ids = {item.observation_id for item in snapshot.observations}
        assert front_obs.observation_id in observation_ids
        assert back_obs.observation_id in observation_ids

        combined = _combined_observation(
            snapshot, {front_obs.observation_id, back_obs.observation_id}
        )
        assert isinstance(combined.value, OptionChain)
        assert len(combined.value.contracts) == 2  # one contract from each side, both present
        evidence_ids = {item.referenced_id for item in combined.provenance.evidence}
        assert evidence_ids == {front_obs.observation_id, back_obs.observation_id}

        # Resolution still produces exactly one value, built from the
        # combined observation, not from the two raw sources directly.
        assert len(snapshot.resolution_results) == 1
        resolved_ids = set(snapshot.resolution_results[0].consumed_observation_ids)
        assert resolved_ids == {combined.observation_id}

    def test_mixed_providers_both_remain_bounded_and_self_contained(self) -> None:
        """Architect checkpoint requirement: when front and back succeed
        through *different* providers, the combined observation's own
        provenance reflects only the primary (front) provider -- so the
        secondary provider's own raw observation and metadata must not
        disappear from the sealed snapshot.
        """
        front_result, front_obs = _successful_result("tradier", date(2026, 8, 21), suffix="front")
        back_result, back_obs = _successful_result("finnhub", date(2026, 9, 18), suffix="back")

        coalesced = coalesce_option_chain_results(
            (front_result, back_result),
            subject=_subject(),
            combined_request=_request(),
            observed_at=NOW,
        )
        assert len(coalesced.attempts) == 2  # no synthetic attempt was fabricated

        snapshot = seal_subject_snapshot(
            (coalesced,),
            as_of=NOW,
            required_capabilities=(MarketCapability.OPTION_CHAIN_V1,),
            resolution_policy_by_capability={
                MarketCapability.OPTION_CHAIN_V1: ResolutionPolicy(
                    "v1", ("tradier", "finnhub"), 3600, ("contracts",)
                )
            },
            provider_metadata=(_provider_metadata("tradier"), _provider_metadata("finnhub")),
        )

        observation_ids = {item.observation_id for item in snapshot.observations}
        assert front_obs.observation_id in observation_ids  # tradier's own raw observation
        assert back_obs.observation_id in observation_ids  # finnhub's own raw observation

        provider_ids = {item.provenance.provider_id for item in snapshot.observations}
        assert provider_ids == {"tradier", "finnhub"}

        metadata_provider_ids = {item.identity.provider_id for item in snapshot.provider_metadata}
        assert metadata_provider_ids == {"tradier", "finnhub"}

        combined = _combined_observation(
            snapshot, {front_obs.observation_id, back_obs.observation_id}
        )
        evidence_ids = {item.referenced_id for item in combined.provenance.evidence}
        assert evidence_ids == {front_obs.observation_id, back_obs.observation_id}

        assert len(snapshot.resolution_results) == 1
        assert snapshot.completeness.resolved_capabilities == (MarketCapability.OPTION_CHAIN_V1,)

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
        # Only the successful side has any observation to contribute (a
        # failed attempt carries none) -- front's raw observation plus the
        # combined one, never a fabricated observation for the failed side.
        assert len(snapshot.observations) == 2
        combined = _combined_observation(snapshot, {front_obs.observation_id})
        assert isinstance(combined.value, OptionChain)
        assert len(combined.value.contracts) == 1  # only the successful side's contract
        evidence_ids = {item.referenced_id for item in combined.provenance.evidence}
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
