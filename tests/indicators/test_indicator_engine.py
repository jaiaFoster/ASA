"""ASA-CORE-004: indicator engine tests, including pinned regression vectors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.canonical_fact import CanonicalFact
from domain.provenance import Provenance
from domain.references import Confidence, EvidenceKind
from indicators.engine import compute_indicator, indicator_identity
from indicators.errors import UnknownIndicatorTypeError
from indicators.registry import DEFAULT_REGISTRY

T0 = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)


def _fact(i: int, price: str) -> CanonicalFact:
    t = T0 + timedelta(minutes=i)
    return CanonicalFact(
        fact_id=f"fact-{i}", version=1, fact_type="market_price",
        value=(("currency", "USD"), ("price", Decimal(price)), ("symbol", "AAPL")),
        confidence=Confidence(score=1.0),
        provenance=Provenance(
            contributing_observation_ids=(f"o{i}",), contributing_provider_ids=("p1",),
            selected_provider_id="p1", disagreements=(), reconciled_at=t),
        effective_time=t, created_time=t,
    )


PRICES = ["200", "201", "202", "203", "204"]


def _facts(n: int = 5) -> tuple[CanonicalFact, ...]:
    return tuple(_fact(i, PRICES[i]) for i in range(n))


class TestComputeIndicatorBasics:
    def test_first_computation_is_version_1(self):
        facts = _facts()
        ind, is_new = compute_indicator(
            "latest_price", facts, T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert is_new
        assert ind.version == 1

    def test_produces_immutable_indicator(self):
        facts = _facts()
        ind, _ = compute_indicator(
            "latest_price", facts, T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        with pytest.raises(Exception):
            ind.version = 2

    def test_unknown_indicator_type_raises(self):
        with pytest.raises(UnknownIndicatorTypeError):
            compute_indicator("nonexistent_indicator", _facts(),
                              T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))

    def test_provenance_lineage_complete(self):
        facts = _facts(3)
        ind, _ = compute_indicator(
            "simple_moving_average", facts, T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2), params={"period": 3})
        assert len(ind.computed_from) == 3
        cited_ids = {ref.referenced_id for ref in ind.computed_from}
        assert cited_ids == {"fact-0", "fact-1", "fact-2"}
        for ref in ind.computed_from:
            assert ref.kind == EvidenceKind.CANONICAL_FACT
            assert ref.version == 1

    def test_provenance_cites_only_facts_actually_used(self):
        """A 3-period SMA over 5 candidate facts cites only the 3 it used."""
        facts = _facts(5)
        ind, _ = compute_indicator(
            "simple_moving_average", facts, T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        cited_ids = {ref.referenced_id for ref in ind.computed_from}
        assert cited_ids == {"fact-2", "fact-3", "fact-4"}
        assert "fact-0" not in cited_ids
        assert "fact-1" not in cited_ids

    def test_provenance_deterministic_ordering(self):
        facts = _facts(3)
        ind_a, _ = compute_indicator(
            "simple_moving_average", facts, T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2), params={"period": 3})
        ind_b, _ = compute_indicator(
            "simple_moving_average", tuple(reversed(facts)), T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2), params={"period": 3})
        assert ind_a.computed_from == ind_b.computed_from

    def test_logic_version_pinned(self):
        facts = _facts()
        ind, _ = compute_indicator(
            "latest_price", facts, T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert ind.logic_version == DEFAULT_REGISTRY.get("latest_price").logic_version


class TestDeterminismAndReplay:
    def test_identical_facts_produce_identical_indicators(self):
        facts = _facts()
        a, _ = compute_indicator(
            "simple_moving_average", facts, T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        b, _ = compute_indicator(
            "simple_moving_average", facts, T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        assert a == b

    def test_replay_byte_identical(self):
        facts = _facts()
        first, _ = compute_indicator(
            "rolling_high", facts, T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        replay, _ = compute_indicator(
            "rolling_high", facts, T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        assert first.indicator_id == replay.indicator_id
        assert first.value == replay.value
        assert first.computed_from == replay.computed_from

    def test_deterministic_execution_order(self):
        facts = _facts()
        shuffled = tuple(reversed(facts))
        a, _ = compute_indicator(
            "exponential_moving_average", facts, T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        b, _ = compute_indicator(
            "exponential_moving_average", shuffled, T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        assert a.value == b.value
        assert a.indicator_id == b.indicator_id

    def test_deterministic_identities(self):
        facts = _facts()
        a, _ = compute_indicator(
            "latest_price", facts, T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        b, _ = compute_indicator(
            "latest_price", facts, T0 + timedelta(minutes=4), T0 + timedelta(minutes=4))
        assert a.indicator_id == b.indicator_id


class TestVersioning:
    def test_changed_value_increments_version(self):
        facts1 = _facts(3)
        ind1, _ = compute_indicator(
            "latest_price", facts1, T0 + timedelta(minutes=2), T0 + timedelta(minutes=2))
        facts2 = _facts(4)
        ind2, is_new = compute_indicator(
            "latest_price", facts2, T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2), previous_indicator=ind1)
        assert is_new
        assert ind2.version == ind1.version + 1

    def test_identical_replay_does_not_increment_version(self):
        facts = _facts(3)
        ind1, _ = compute_indicator(
            "latest_price", facts, T0 + timedelta(minutes=2), T0 + timedelta(minutes=2))
        ind2, is_new = compute_indicator(
            "latest_price", facts, T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2), previous_indicator=ind1)
        assert not is_new
        assert ind2.version == ind1.version
        assert ind2.value == ind1.value

    def test_no_stale_provenance_on_replay_with_new_evidence(self):
        """A later call in the same group, with the same resolved value but
        a different created_time, must reflect THIS call's created_time —
        never a verbatim stale copy of the previous object (ASA-CORE-005
        Phase 0). effective_time stays fixed (same group); only
        created_time (the "computed at" wall-clock time) advances."""
        facts = _facts(1)  # just fact-0, price 200
        ind1, _ = compute_indicator("latest_price", facts, T0, T0)
        ind2, is_new = compute_indicator(
            "latest_price", facts, T0,
            T0 + timedelta(minutes=10), previous_indicator=ind1)
        assert not is_new
        assert ind2.version == ind1.version
        # created_time reflects THIS call, not the stale original
        assert ind2.created_time == T0 + timedelta(minutes=10)
        assert ind2.created_time != ind1.created_time


class TestIndicatorIdentity:
    def test_same_input_same_id(self):
        a = indicator_identity("latest_price", ("f1", "f2"), T0, Decimal("100"))
        b = indicator_identity("latest_price", ("f1", "f2"), T0, Decimal("100"))
        assert a == b

    def test_fact_id_order_does_not_change_identity(self):
        a = indicator_identity("latest_price", ("f1", "f2"), T0, Decimal("100"))
        b = indicator_identity("latest_price", ("f2", "f1"), T0, Decimal("100"))
        assert a == b

    def test_different_type_different_id(self):
        a = indicator_identity("latest_price", ("f1",), T0, Decimal("100"))
        b = indicator_identity("rolling_high", ("f1",), T0, Decimal("100"))
        assert a != b

    def test_different_source_facts_different_id(self):
        a = indicator_identity("latest_price", ("f1",), T0, Decimal("100"))
        b = indicator_identity("latest_price", ("f1", "f2"), T0, Decimal("100"))
        assert a != b

    def test_different_time_different_id(self):
        a = indicator_identity("latest_price", ("f1",), T0, Decimal("100"))
        b = indicator_identity("latest_price", ("f1",), T0 + timedelta(minutes=1), Decimal("100"))
        assert a != b

    def test_different_value_different_id(self):
        a = indicator_identity("latest_price", ("f1",), T0, Decimal("100"))
        b = indicator_identity("latest_price", ("f1",), T0, Decimal("101"))
        assert a != b

    def test_output_is_lowercase_hex_sha256(self):
        fid = indicator_identity("latest_price", ("f1",), T0, Decimal("100"))
        assert len(fid) == 64
        assert fid == fid.lower()
        int(fid, 16)


# ---------------------------------------------------------------------------
# Pinned regression vectors
# ---------------------------------------------------------------------------

class TestPinnedIndicatorVectors:
    def _sma_group(self):
        return _facts()

    def test_pinned_sma_indicator_id(self):
        ind, _ = compute_indicator(
            "simple_moving_average", self._sma_group(), T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        assert ind.indicator_id == (
            "a0b8c2316e357082e31a20929ce439cbee143078ab880919e14d1c9bf5dfc06f"
        )

    def test_pinned_sma_value(self):
        ind, _ = compute_indicator(
            "simple_moving_average", self._sma_group(), T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        assert ind.value == Decimal("203")

    def test_pinned_provenance_vector(self):
        ind, _ = compute_indicator(
            "simple_moving_average", self._sma_group(), T0 + timedelta(minutes=4),
            T0 + timedelta(minutes=4), params={"period": 3})
        cited_ids = tuple(ref.referenced_id for ref in ind.computed_from)
        assert cited_ids == ("fact-2", "fact-3", "fact-4")
