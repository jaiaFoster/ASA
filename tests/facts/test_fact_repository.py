"""ASA-CORE-003: Canonical Fact repository tests."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.canonical_fact import CanonicalFact
from domain.observation import Observation
from domain.provenance import Provenance
from domain.references import Confidence
from facts.errors import (
    DuplicateFactError,
    FactIdentityCollisionError,
    FactNotFoundError,
    NonMonotonicVersionError,
)
from facts.repository import InMemoryCanonicalFactRepository

T = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
T2 = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)
RT = datetime(2026, 7, 21, 14, 31, tzinfo=timezone.utc)

V1 = (("currency", "USD"), ("price", Decimal("201.55")), ("symbol", "AAPL"))
V2 = (("currency", "USD"), ("price", Decimal("201.60")), ("symbol", "AAPL"))


def _obs(oid: str, provider: str, value: object, effective_time: datetime = T,
         otype: str = "market_price") -> Observation:
    return Observation(observation_id=oid, observation_type=otype,
                       provider_id=provider, value=value,
                       effective_time=effective_time, recorded_time=RT)


def _fact(fact_id: str, version: int, fact_type: str = "market_price",
          value: object = V1, effective_time: datetime = T) -> CanonicalFact:
    return CanonicalFact(
        fact_id=fact_id, version=version, fact_type=fact_type, value=value,
        confidence=Confidence(score=1.0),
        provenance=Provenance(
            contributing_observation_ids=("o1",), contributing_provider_ids=("p1",),
            selected_provider_id="p1", disagreements=(), reconciled_at=RT),
        effective_time=effective_time, created_time=RT,
    )


class TestAppendAndLatest:
    def test_append_then_latest(self):
        repo = InMemoryCanonicalFactRepository()
        fact = _fact("f1", 1)
        repo.append(fact)
        assert repo.latest("market_price", T) == fact

    def test_latest_missing_raises(self):
        repo = InMemoryCanonicalFactRepository()
        with pytest.raises(FactNotFoundError):
            repo.latest("market_price", T)

    def test_no_update_or_delete_operations(self):
        repo = InMemoryCanonicalFactRepository()
        for forbidden in ("update", "delete", "remove", "clear", "replace"):
            assert not hasattr(repo, forbidden)


class TestHistory:
    def test_history_version_ordered(self):
        repo = InMemoryCanonicalFactRepository()
        repo.append(_fact("f1", 1, value=V1))
        repo.append(_fact("f2", 2, value=V2))
        history = repo.history("market_price", T)
        assert [f.version for f in history] == [1, 2]

    def test_history_empty_for_unknown_group(self):
        repo = InMemoryCanonicalFactRepository()
        assert repo.history("market_price", T) == ()

    def test_history_immutable(self):
        repo = InMemoryCanonicalFactRepository()
        repo.append(_fact("f1", 1))
        history = repo.history("market_price", T)
        assert isinstance(history, tuple)
        with pytest.raises(TypeError):
            history[0] = _fact("f2", 2)


class TestVersionMonotonicity:
    def test_first_version_must_be_1(self):
        repo = InMemoryCanonicalFactRepository()
        with pytest.raises(NonMonotonicVersionError):
            repo.append(_fact("f1", 2))

    def test_version_must_increment_by_exactly_1(self):
        repo = InMemoryCanonicalFactRepository()
        repo.append(_fact("f1", 1, value=V1))
        with pytest.raises(NonMonotonicVersionError):
            repo.append(_fact("f2", 3, value=V2))

    def test_correct_sequential_versions_accepted(self):
        repo = InMemoryCanonicalFactRepository()
        repo.append(_fact("f1", 1, value=V1))
        repo.append(_fact("f2", 2, value=V2))
        assert repo.latest("market_price", T).version == 2


class TestDuplicateBehavior:
    def test_duplicate_append_rejected(self):
        repo = InMemoryCanonicalFactRepository()
        fact = _fact("f1", 1)
        repo.append(fact)
        with pytest.raises(DuplicateFactError):
            repo.append(fact)

    def test_identity_collision_rejected(self):
        repo = InMemoryCanonicalFactRepository()
        original = _fact("f1", 1)
        repo.append(original)
        colliding = dataclasses.replace(original, confidence=Confidence(score=0.1))
        with pytest.raises(FactIdentityCollisionError):
            repo.append(colliding)

    def test_original_preserved_after_collision_rejection(self):
        repo = InMemoryCanonicalFactRepository()
        original = _fact("f1", 1)
        repo.append(original)
        colliding = dataclasses.replace(original, confidence=Confidence(score=0.1))
        with pytest.raises(FactIdentityCollisionError):
            repo.append(colliding)
        assert repo.latest("market_price", T) == original
        assert repo.latest("market_price", T).confidence.score == 1.0


class TestQuerySemantics:
    def _filled(self) -> InMemoryCanonicalFactRepository:
        repo = InMemoryCanonicalFactRepository()
        repo.append(_fact("f1", 1, fact_type="market_price", value=V1, effective_time=T))
        repo.append(_fact("f2", 1, fact_type="quote", value=V1, effective_time=T))
        repo.append(_fact("f3", 2, fact_type="market_price", value=V2, effective_time=T))
        repo.append(_fact("f4", 1, fact_type="market_price", value=V1, effective_time=T2))
        return repo

    def test_by_type_insertion_order(self):
        repo = self._filled()
        assert [f.fact_id for f in repo.by_type("market_price")] == ["f1", "f3", "f4"]

    def test_by_effective_time_insertion_order(self):
        repo = self._filled()
        assert [f.fact_id for f in repo.by_effective_time(T)] == ["f1", "f2", "f3"]

    def test_returned_collections_are_tuples(self):
        repo = self._filled()
        assert isinstance(repo.by_type("market_price"), tuple)
        assert isinstance(repo.by_effective_time(T), tuple)
        assert isinstance(repo.history("market_price", T), tuple)


class TestReconcileAndAppend:
    def test_new_version_appended(self):
        repo = InMemoryCanonicalFactRepository()
        group = (_obs("o1", "p1", V1),)
        fact = repo.reconcile_and_append(group, RT)
        assert fact is not None
        assert fact.version == 1
        assert repo.latest("market_price", T) == fact

    def test_idempotent_replay_returns_none_and_does_not_append(self):
        repo = InMemoryCanonicalFactRepository()
        group = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        first = repo.reconcile_and_append(group, RT)
        replay = repo.reconcile_and_append(group, RT)
        assert replay is None
        assert len(repo.history("market_price", T)) == 1

    def test_changed_value_produces_new_version(self):
        repo = InMemoryCanonicalFactRepository()
        group1 = (_obs("o1", "p1", V1),)
        repo.reconcile_and_append(group1, RT)
        group2 = (_obs("o1", "p1", V1), _obs("o2", "p2", V2), _obs("o3", "p3", V2))
        fact2 = repo.reconcile_and_append(group2, RT)
        assert fact2.version == 2

    def test_empty_observations_raises(self):
        repo = InMemoryCanonicalFactRepository()
        from reconciliation.errors import EmptyObservationGroupError
        with pytest.raises(EmptyObservationGroupError):
            repo.reconcile_and_append((), RT)
