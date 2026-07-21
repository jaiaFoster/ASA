"""ASA-CORE-002: append-only Observation repository tests."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from domain.observation import Observation
from observation import (
    DuplicateObservationError,
    IdentityCollisionError,
    InMemoryObservationRepository,
    ObservationNotFoundError,
)

T0 = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def _obs(i: int, provider: str = "prov-a", otype: str = "market_price",
         offset_minutes: int = 0) -> Observation:
    return Observation(
        observation_id=f"id-{i}",
        observation_type=otype,
        provider_id=provider,
        value=i,
        effective_time=T0 + timedelta(minutes=offset_minutes),
        recorded_time=T0,
    )


class TestAppendAndGet:
    def test_append_then_retrieve(self):
        repo = InMemoryObservationRepository()
        obs = _obs(1)
        repo.append(obs)
        assert repo.get("id-1") == obs

    def test_exists(self):
        repo = InMemoryObservationRepository()
        repo.append(_obs(1))
        assert repo.exists("id-1")
        assert not repo.exists("id-2")

    def test_missing_get_raises_explicit_error(self):
        repo = InMemoryObservationRepository()
        with pytest.raises(ObservationNotFoundError):
            repo.get("nope")

    def test_no_update_or_delete_operations(self):
        repo = InMemoryObservationRepository()
        for forbidden in ("update", "delete", "remove", "clear", "replace"):
            assert not hasattr(repo, forbidden), f"repository must not offer {forbidden}"


class TestDuplicateBehavior:
    def test_duplicate_append_rejected(self):
        repo = InMemoryObservationRepository()
        obs = _obs(1)
        repo.append(obs)
        with pytest.raises(DuplicateObservationError):
            repo.append(obs)

    def test_identity_collision_rejected(self):
        repo = InMemoryObservationRepository()
        original = _obs(1)
        repo.append(original)
        colliding = dataclasses.replace(original, value=999)
        with pytest.raises(IdentityCollisionError):
            repo.append(colliding)

    def test_original_preserved_after_rejection(self):
        repo = InMemoryObservationRepository()
        original = _obs(1)
        repo.append(original)
        with pytest.raises(IdentityCollisionError):
            repo.append(dataclasses.replace(original, value=999))
        assert repo.get("id-1") == original
        assert repo.get("id-1").value == 1


class TestQuerySemantics:
    def _filled(self) -> InMemoryObservationRepository:
        repo = InMemoryObservationRepository()
        repo.append(_obs(1, provider="prov-a", otype="market_price", offset_minutes=0))
        repo.append(_obs(2, provider="prov-b", otype="quote", offset_minutes=10))
        repo.append(_obs(3, provider="prov-a", otype="quote", offset_minutes=20))
        repo.append(_obs(4, provider="prov-b", otype="market_price", offset_minutes=30))
        return repo

    def test_all_insertion_order(self):
        repo = self._filled()
        assert [o.observation_id for o in repo.all()] == ["id-1", "id-2", "id-3", "id-4"]

    def test_by_provider_insertion_order(self):
        repo = self._filled()
        assert [o.observation_id for o in repo.by_provider("prov-a")] == ["id-1", "id-3"]

    def test_by_type_insertion_order(self):
        repo = self._filled()
        assert [o.observation_id for o in repo.by_type("market_price")] == ["id-1", "id-4"]

    def test_time_range_inclusive_start_exclusive_end(self):
        repo = self._filled()
        start = T0 + timedelta(minutes=10)
        end = T0 + timedelta(minutes=30)
        result = [o.observation_id for o in repo.by_time_range(start, end)]
        assert result == ["id-2", "id-3"]  # id-2 at start included, id-4 at end excluded

    def test_time_range_preserves_insertion_order(self):
        repo = InMemoryObservationRepository()
        # Insert out of effective-time order
        repo.append(_obs(1, offset_minutes=20))
        repo.append(_obs(2, offset_minutes=0))
        result = [o.observation_id for o in
                  repo.by_time_range(T0, T0 + timedelta(minutes=60))]
        assert result == ["id-1", "id-2"]  # insertion order, not time order

    def test_empty_queries_return_empty_tuples(self):
        repo = InMemoryObservationRepository()
        assert repo.all() == ()
        assert repo.by_provider("x") == ()
        assert repo.by_type("x") == ()


class TestReturnedCollectionsImmutable:
    def test_returned_collections_are_tuples(self):
        repo = InMemoryObservationRepository()
        repo.append(_obs(1))
        assert isinstance(repo.all(), tuple)
        assert isinstance(repo.by_provider("prov-a"), tuple)
        assert isinstance(repo.by_type("market_price"), tuple)
        assert isinstance(repo.by_time_range(T0, T0 + timedelta(minutes=1)), tuple)

    def test_returned_collection_cannot_mutate_repository(self):
        repo = InMemoryObservationRepository()
        repo.append(_obs(1))
        snapshot = repo.all()
        with pytest.raises(TypeError):
            snapshot[0] = _obs(2)  # tuples do not support item assignment
        assert repo.all() == snapshot

    def test_stored_records_are_immutable(self):
        repo = InMemoryObservationRepository()
        repo.append(_obs(1))
        with pytest.raises(dataclasses.FrozenInstanceError):
            repo.get("id-1").value = 999
