"""ASA-CORE-004: Indicator repository tests."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.indicator import Indicator
from domain.references import EvidenceKind, EvidenceReference
from indicators.errors import (
    DuplicateIndicatorError,
    IndicatorIdentityCollisionError,
    IndicatorNotFoundError,
    NonMonotonicIndicatorVersionError,
)
from indicators.repository import InMemoryIndicatorRepository

T = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
T2 = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)


def _ref(fact_id: str, version: int = 1) -> EvidenceReference:
    return EvidenceReference(kind=EvidenceKind.CANONICAL_FACT, referenced_id=fact_id, version=version)


def _indicator(indicator_id: str, version: int, indicator_type: str = "latest_price",
              value: object = Decimal("100"), effective_time: datetime = T,
              computed_from: tuple = None) -> Indicator:
    return Indicator(
        indicator_id=indicator_id, version=version, indicator_type=indicator_type,
        logic_version="v1", value=value,
        computed_from=computed_from if computed_from is not None else (_ref("fact-1"),),
        effective_time=effective_time, created_time=effective_time,
    )


class TestAppendAndLatest:
    def test_append_then_latest(self):
        repo = InMemoryIndicatorRepository()
        ind = _indicator("i1", 1)
        repo.append(ind)
        assert repo.latest("latest_price", T) == ind

    def test_latest_missing_raises(self):
        repo = InMemoryIndicatorRepository()
        with pytest.raises(IndicatorNotFoundError):
            repo.latest("latest_price", T)

    def test_no_update_or_delete_operations(self):
        repo = InMemoryIndicatorRepository()
        for forbidden in ("update", "delete", "remove", "clear", "replace"):
            assert not hasattr(repo, forbidden)


class TestHistory:
    def test_history_version_ordered(self):
        repo = InMemoryIndicatorRepository()
        repo.append(_indicator("i1", 1, value=Decimal("100")))
        repo.append(_indicator("i2", 2, value=Decimal("101")))
        history = repo.history("latest_price", T)
        assert [i.version for i in history] == [1, 2]

    def test_history_empty_for_unknown_group(self):
        repo = InMemoryIndicatorRepository()
        assert repo.history("latest_price", T) == ()

    def test_history_immutable(self):
        repo = InMemoryIndicatorRepository()
        repo.append(_indicator("i1", 1))
        history = repo.history("latest_price", T)
        assert isinstance(history, tuple)
        with pytest.raises(TypeError):
            history[0] = _indicator("i2", 2)


class TestVersionMonotonicity:
    def test_first_version_must_be_1(self):
        repo = InMemoryIndicatorRepository()
        with pytest.raises(NonMonotonicIndicatorVersionError):
            repo.append(_indicator("i1", 2))

    def test_version_must_increment_by_exactly_1(self):
        repo = InMemoryIndicatorRepository()
        repo.append(_indicator("i1", 1, value=Decimal("100")))
        with pytest.raises(NonMonotonicIndicatorVersionError):
            repo.append(_indicator("i2", 3, value=Decimal("101")))

    def test_correct_sequential_versions_accepted(self):
        repo = InMemoryIndicatorRepository()
        repo.append(_indicator("i1", 1, value=Decimal("100")))
        repo.append(_indicator("i2", 2, value=Decimal("101")))
        assert repo.latest("latest_price", T).version == 2


class TestDuplicateBehavior:
    def test_duplicate_append_rejected(self):
        repo = InMemoryIndicatorRepository()
        ind = _indicator("i1", 1)
        repo.append(ind)
        with pytest.raises(DuplicateIndicatorError):
            repo.append(ind)

    def test_identity_collision_rejected(self):
        repo = InMemoryIndicatorRepository()
        original = _indicator("i1", 1)
        repo.append(original)
        colliding = dataclasses.replace(original, logic_version="v2")
        with pytest.raises(IndicatorIdentityCollisionError):
            repo.append(colliding)

    def test_original_preserved_after_collision_rejection(self):
        repo = InMemoryIndicatorRepository()
        original = _indicator("i1", 1)
        repo.append(original)
        colliding = dataclasses.replace(original, logic_version="v2")
        with pytest.raises(IndicatorIdentityCollisionError):
            repo.append(colliding)
        assert repo.latest("latest_price", T) == original
        assert repo.latest("latest_price", T).logic_version == "v1"


class TestQuerySemantics:
    def _filled(self) -> InMemoryIndicatorRepository:
        repo = InMemoryIndicatorRepository()
        repo.append(_indicator("i1", 1, indicator_type="latest_price",
                               effective_time=T, computed_from=(_ref("fact-1"),)))
        repo.append(_indicator("i2", 1, indicator_type="rolling_high",
                               effective_time=T, computed_from=(_ref("fact-1"), _ref("fact-2"))))
        repo.append(_indicator("i3", 2, indicator_type="latest_price",
                               value=Decimal("101"), effective_time=T, computed_from=(_ref("fact-2"),)))
        repo.append(_indicator("i4", 1, indicator_type="latest_price",
                               effective_time=T2, computed_from=(_ref("fact-3"),)))
        return repo

    def test_by_indicator_type_insertion_order(self):
        repo = self._filled()
        assert [i.indicator_id for i in repo.by_indicator_type("latest_price")] == \
            ["i1", "i3", "i4"]

    def test_by_fact_finds_all_citing_indicators(self):
        repo = self._filled()
        assert [i.indicator_id for i in repo.by_fact("fact-1")] == ["i1", "i2"]
        assert [i.indicator_id for i in repo.by_fact("fact-2")] == ["i2", "i3"]

    def test_by_fact_empty_for_uncited_fact(self):
        repo = self._filled()
        assert repo.by_fact("fact-999") == ()

    def test_returned_collections_are_tuples(self):
        repo = self._filled()
        assert isinstance(repo.by_indicator_type("latest_price"), tuple)
        assert isinstance(repo.by_fact("fact-1"), tuple)
        assert isinstance(repo.history("latest_price", T), tuple)
