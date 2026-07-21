"""ASA-CORE-003: reconciliation engine tests, including pinned regression vectors."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.canonical_fact import CanonicalFact
from domain.observation import Observation
from domain.provenance import Provenance
from domain.references import Confidence
from reconciliation.engine import reconcile
from reconciliation.errors import InconsistentGroupError

T = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
RT = datetime(2026, 7, 21, 14, 31, tzinfo=timezone.utc)
RT2 = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)

V1 = (("currency", "USD"), ("price", Decimal("201.55")), ("symbol", "AAPL"))
V2 = (("currency", "USD"), ("price", Decimal("201.60")), ("symbol", "AAPL"))


def _obs(oid: str, provider: str, value: object) -> Observation:
    return Observation(observation_id=oid, observation_type="market_price",
                       provider_id=provider, value=value,
                       effective_time=T, recorded_time=RT)


def _fact(**overrides) -> CanonicalFact:
    kwargs = dict(
        fact_id="stub", version=1, fact_type="market_price", value=V1,
        confidence=Confidence(score=1.0),
        provenance=Provenance(
            contributing_observation_ids=("o1",), contributing_provider_ids=("p1",),
            selected_provider_id="p1", disagreements=(), reconciled_at=RT),
        effective_time=T, created_time=RT,
    )
    kwargs.update(overrides)
    return CanonicalFact(**kwargs)


class TestReconcileBasics:
    def test_first_reconciliation_is_version_1(self):
        group = (_obs("o1", "p1", V1),)
        fact, is_new = reconcile(group, RT)
        assert is_new
        assert fact.version == 1

    def test_reconcile_produces_immutable_fact(self):
        group = (_obs("o1", "p1", V1),)
        fact, _ = reconcile(group, RT)
        with pytest.raises(Exception):
            fact.version = 2

    def test_provenance_complete(self):
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V1), _obs("o3", "p3", V2))
        fact, _ = reconcile(group, RT)
        prov = fact.provenance
        assert prov.contributing_observation_ids == ("o1", "o2", "o3")
        assert prov.contributing_provider_ids == ("p1", "p2", "p3")
        assert prov.selected_provider_id in ("p1", "p2")
        assert len(prov.disagreements) == 1
        assert prov.reconciled_at == RT

    def test_mismatched_previous_fact_type_raises(self):
        group = (_obs("o1", "p1", V1),)
        previous = _fact(fact_type="other_type")
        with pytest.raises(InconsistentGroupError):
            reconcile(group, RT, previous_fact=previous)

    def test_mismatched_previous_effective_time_raises(self):
        group = (_obs("o1", "p1", V1),)
        previous = _fact(effective_time=RT2)
        with pytest.raises(InconsistentGroupError):
            reconcile(group, RT, previous_fact=previous)


class TestDeterminismAndReplay:
    def test_identical_observations_reconcile_identically(self):
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        fact_a, _ = reconcile(group, RT)
        fact_b, _ = reconcile(group, RT)
        assert fact_a == fact_b

    def test_observation_ordering_does_not_change_result(self):
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V1), _obs("o3", "p3", V2))
        fact_forward, _ = reconcile(group, RT)
        fact_backward, _ = reconcile(tuple(reversed(group)), RT)
        assert fact_forward == fact_backward

    def test_replay_produces_byte_identical_facts(self):
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V2), _obs("o3", "p3", V2))
        first, _ = reconcile(group, RT)
        replay, _ = reconcile(group, RT)
        assert first.fact_id == replay.fact_id
        assert first.value == replay.value
        assert first.confidence == replay.confidence
        assert first.provenance == replay.provenance

    def test_conflicting_observations_generate_disagreements(self):
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V2))
        fact, _ = reconcile(group, RT)
        assert len(fact.provenance.disagreements) == 1

    def test_confidence_deterministic_across_calls(self):
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        a, _ = reconcile(group, RT)
        b, _ = reconcile(group, RT)
        assert a.confidence.score == b.confidence.score


class TestVersioning:
    def test_first_version_equals_1(self):
        group = (_obs("o1", "p1", V1),)
        fact, _ = reconcile(group, RT)
        assert fact.version == 1

    def test_changed_value_increments_version(self):
        group1 = (_obs("o1", "p1", V1),)
        fact1, _ = reconcile(group1, RT)
        group2 = (_obs("o1", "p1", V1), _obs("o2", "p2", V2), _obs("o3", "p3", V2))
        fact2, is_new = reconcile(group2, RT2, previous_fact=fact1)
        assert is_new
        assert fact2.version == fact1.version + 1
        assert fact2.value != fact1.value

    def test_identical_replay_does_not_increment_version(self):
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        fact1, _ = reconcile(group, RT)
        fact2, is_new = reconcile(group, RT2, previous_fact=fact1)
        assert not is_new
        assert fact2 is fact1
        assert fact2.version == fact1.version

    def test_new_corroborating_evidence_same_value_no_version_bump(self):
        group1 = (_obs("o1", "p1", V1),)
        fact1, _ = reconcile(group1, RT)
        group2 = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        fact2, is_new = reconcile(group2, RT2, previous_fact=fact1)
        assert not is_new  # same resolved value -> no new version


# ---------------------------------------------------------------------------
# Pinned regression vectors — a failure here means engine behavior changed.
# ---------------------------------------------------------------------------

class TestPinnedReconciliationVectors:
    PINNED_FACT_ID = "cb7cd96706fac8fc183dbcee9c29a5050f060a23152b8aeae7665e20e3f2eaaf"
    PINNED_CONFIDENCE = 2 / 3

    def _group(self):
        return (_obs("o1", "prov-a", V1), _obs("o2", "prov-b", V1), _obs("o3", "prov-c", V2))

    def test_pinned_fact_id(self):
        fact, _ = reconcile(self._group(), RT)
        assert fact.fact_id == self.PINNED_FACT_ID

    def test_pinned_confidence(self):
        fact, _ = reconcile(self._group(), RT)
        assert fact.confidence.score == pytest.approx(self.PINNED_CONFIDENCE)

    def test_pinned_provenance_shape(self):
        fact, _ = reconcile(self._group(), RT)
        assert fact.provenance.contributing_observation_ids == ("o1", "o2", "o3")
        assert fact.provenance.contributing_provider_ids == ("prov-a", "prov-b", "prov-c")
        assert fact.provenance.selected_provider_id == "prov-a"
        assert len(fact.provenance.disagreements) == 1
        assert fact.provenance.disagreements[0].provider_id == "prov-c"

    def test_pinned_resolved_value(self):
        fact, _ = reconcile(self._group(), RT)
        assert fact.value == V1

    def test_pinned_version(self):
        fact, _ = reconcile(self._group(), RT)
        assert fact.version == 1
