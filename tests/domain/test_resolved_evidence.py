"""SPRINT-014 S14-PR-05A: ResolvedCapabilityEvidence -- the restricted,
provider-blind projection a pure strategy expansion function receives.
"""

from __future__ import annotations

import pytest

from domain import EvidenceUsability, ResolvedCapabilityEvidence
from domain.market_data import FreshnessStatus, MarketCapability
from domain.values import DomainInvariantError


class TestResolvedCapabilityEvidence:
    def test_resolved_requires_a_value(self) -> None:
        with pytest.raises(DomainInvariantError, match="value is required"):
            ResolvedCapabilityEvidence(
                "demand-1",
                MarketCapability.REAL_TIME_QUOTE_V1,
                EvidenceUsability.RESOLVED,
                None,
                (),
                FreshnessStatus.FRESH,
            )

    def test_unknown_forbids_a_value(self) -> None:
        with pytest.raises(DomainInvariantError, match="must be absent"):
            ResolvedCapabilityEvidence(
                "demand-1",
                MarketCapability.REAL_TIME_QUOTE_V1,
                EvidenceUsability.UNKNOWN,
                object(),
                (),
                None,
            )

    def test_demand_id_must_be_normalized(self) -> None:
        with pytest.raises(DomainInvariantError, match="demand_id"):
            ResolvedCapabilityEvidence(
                " padded",
                MarketCapability.REAL_TIME_QUOTE_V1,
                EvidenceUsability.UNKNOWN,
                None,
                (),
                None,
            )

    def test_unknown_with_no_value_and_no_freshness_is_valid(self) -> None:
        evidence = ResolvedCapabilityEvidence(
            "demand-1",
            MarketCapability.REAL_TIME_QUOTE_V1,
            EvidenceUsability.UNKNOWN,
            None,
            (),
            None,
        )
        assert evidence.value is None
        assert evidence.observation_ids == ()

    def test_resolved_with_a_value_and_observation_ids_is_valid(self) -> None:
        evidence = ResolvedCapabilityEvidence(
            "demand-1",
            MarketCapability.REAL_TIME_QUOTE_V1,
            EvidenceUsability.RESOLVED,
            object(),
            ("obs-1", "obs-2"),
            FreshnessStatus.FRESH,
        )
        assert evidence.observation_ids == ("obs-1", "obs-2")

    def test_carries_no_provider_or_request_field(self) -> None:
        """The one structural guarantee this type's entire purpose rests
        on: nothing here can leak a provider id, a raw attempt, or a
        CapabilityRequest, because no such field exists on the type at all.
        """
        field_names = set(ResolvedCapabilityEvidence.__dataclass_fields__.keys())
        assert field_names == {
            "demand_id",
            "capability",
            "usability",
            "value",
            "observation_ids",
            "freshness_status",
        }
