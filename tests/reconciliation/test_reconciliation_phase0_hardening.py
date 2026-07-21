"""ASA-CORE-006 Phase 0: Adjacent Hardening regression tests.

Resolves GitHub Issue #47 (filed in ASA-CORE-005): reconciliation.engine.
reconcile had the identical stale-provenance pattern already fixed in
indicators.engine.compute_indicator during ASA-CORE-005 Phase 0. This file
proves the fix, mirroring tests/indicators/test_phase0_hardening.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.observation import Observation
from reconciliation.engine import reconcile
from reconciliation.errors import InconsistentGroupError

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _obs(oid: str, provider: str, value: object,
         effective_time: datetime = T0) -> Observation:
    return Observation(
        observation_id=oid, observation_type="market_price", provider_id=provider,
        value=value, effective_time=effective_time, recorded_time=effective_time,
    )


V1 = (("currency", "USD"), ("price", Decimal("100")), ("symbol", "AAPL"))


class TestSemanticReplayComparison:
    def test_canonicalized_values_compare_equal(self):
        group = (_obs("o1", "p1", V1),)
        fact1, _ = reconcile(group, T0)
        fact2, is_new = reconcile(group, T0 + timedelta(minutes=1), previous_fact=fact1)
        assert not is_new
        assert fact2.version == fact1.version

    def test_value_stored_is_canonicalized(self):
        from domain.canonicalization import canonicalize_value
        group = (_obs("o1", "p1", V1),)
        fact, _ = reconcile(group, T0)
        assert fact.value == canonicalize_value(fact.value)


class TestStaleProvenanceElimination:
    def test_replay_reflects_current_call_created_time(self):
        """A no-new-version result must carry THIS call's created_time, not
        a verbatim copy of the original object's created_time."""
        group = (_obs("o1", "p1", V1),)
        fact1, _ = reconcile(group, T0)
        later = T0 + timedelta(hours=1)
        fact2, is_new = reconcile(group, later, previous_fact=fact1)
        assert not is_new
        assert fact2.created_time == later
        assert fact2.created_time != fact1.created_time
        assert fact2.provenance.reconciled_at == later
        assert fact2.provenance.reconciled_at != fact1.provenance.reconciled_at

    def test_replay_reflects_current_contributing_observations(self):
        """New corroborating evidence (same resolved value, larger
        Observation set) must be cited in the returned object's provenance
        — never a verbatim stale copy of the previous object's provenance."""
        single = (_obs("o1", "p1", V1),)
        fact1, _ = reconcile(single, T0)
        assert fact1.provenance.contributing_observation_ids == ("o1",)

        larger = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        fact2, is_new = reconcile(
            larger, T0 + timedelta(minutes=5), previous_fact=fact1)
        assert not is_new  # same resolved value -> no new version
        assert fact2.provenance.contributing_observation_ids == ("o1", "o2")
        assert fact2.provenance.contributing_observation_ids != \
            fact1.provenance.contributing_observation_ids

    def test_stored_history_never_contains_stale_record(self):
        """The repository only ever stores what callers explicitly append;
        a discarded (is_new_version=False) result must never silently
        become part of persisted history with mismatched provenance."""
        from facts.repository import InMemoryCanonicalFactRepository
        repo = InMemoryCanonicalFactRepository()
        group = (_obs("o1", "p1", V1),)
        fact1 = repo.reconcile_and_append(group, T0)
        assert fact1 is not None

        replay = repo.reconcile_and_append(group, T0 + timedelta(minutes=5))
        assert replay is None  # caller correctly does not persist
        history = repo.history("market_price", T0)
        assert len(history) == 1
        assert history[0] == fact1


class TestPreviousFactGroupConsistency:
    def test_mismatched_fact_type_raises(self):
        group_a = (Observation(observation_id="o1", observation_type="type_a",
                               provider_id="p1", value=V1,
                               effective_time=T0, recorded_time=T0),)
        fact1, _ = reconcile(group_a, T0)
        group_b = (Observation(observation_id="o2", observation_type="type_b",
                               provider_id="p1", value=V1,
                               effective_time=T0, recorded_time=T0),)
        with pytest.raises(InconsistentGroupError):
            reconcile(group_b, T0, previous_fact=fact1)

    def test_mismatched_effective_time_raises(self):
        group = (_obs("o1", "p1", V1),)
        fact1, _ = reconcile(group, T0)
        other_time = T0 + timedelta(hours=1)
        group2 = (_obs("o2", "p1", V1, effective_time=other_time),)
        with pytest.raises(InconsistentGroupError):
            reconcile(group2, other_time, previous_fact=fact1)

    def test_matching_group_does_not_raise(self):
        group = (_obs("o1", "p1", V1),)
        fact1, _ = reconcile(group, T0)
        fact2, is_new = reconcile(group, T0 + timedelta(minutes=1), previous_fact=fact1)
        assert not is_new  # does not raise; same group, same value
