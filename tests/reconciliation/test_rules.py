"""ASA-CORE-003: reconciliation rules unit tests."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.observation import Observation
from reconciliation.errors import EmptyObservationGroupError, InconsistentGroupError
from reconciliation.rules import (
    compute_confidence,
    fact_identity,
    group_by_fact_identity,
    require_single_group,
    resolve_value,
)

T = datetime(2026, 7, 21, 14, 30, tzinfo=timezone.utc)
T2 = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)
RT = datetime(2026, 7, 21, 14, 31, tzinfo=timezone.utc)

V1 = (("currency", "USD"), ("price", Decimal("201.55")), ("symbol", "AAPL"))
V2 = (("currency", "USD"), ("price", Decimal("201.60")), ("symbol", "AAPL"))


def _obs(oid: str, provider: str, value: object, otype: str = "market_price",
         effective_time: datetime = T) -> Observation:
    return Observation(observation_id=oid, observation_type=otype,
                       provider_id=provider, value=value,
                       effective_time=effective_time, recorded_time=RT)


class TestGrouping:
    def test_groups_by_type_and_effective_time(self):
        obs = (
            _obs("o1", "p1", V1, otype="a", effective_time=T),
            _obs("o2", "p2", V1, otype="b", effective_time=T),
            _obs("o3", "p3", V1, otype="a", effective_time=T2),
        )
        groups = group_by_fact_identity(obs)
        assert set(groups.keys()) == {("a", T), ("b", T), ("a", T2)}

    def test_grouping_independent_of_order(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V2))
        forward = group_by_fact_identity(obs)
        backward = group_by_fact_identity(tuple(reversed(obs)))
        assert set(forward.keys()) == set(backward.keys())
        for key in forward:
            assert set(o.observation_id for o in forward[key]) == \
                set(o.observation_id for o in backward[key])


class TestRequireSingleGroup:
    def test_empty_raises(self):
        with pytest.raises(EmptyObservationGroupError):
            require_single_group(())

    def test_mixed_type_raises(self):
        obs = (_obs("o1", "p1", V1, otype="a"), _obs("o2", "p2", V1, otype="b"))
        with pytest.raises(InconsistentGroupError):
            require_single_group(obs)

    def test_mixed_effective_time_raises(self):
        obs = (_obs("o1", "p1", V1, effective_time=T), _obs("o2", "p2", V1, effective_time=T2))
        with pytest.raises(InconsistentGroupError):
            require_single_group(obs)

    def test_consistent_group_passes(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        require_single_group(obs)  # does not raise


class TestResolveValue:
    def test_unanimous_agreement(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        value, disagreements, selected = resolve_value(obs)
        assert value == V1
        assert disagreements == ()

    def test_majority_wins(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1), _obs("o3", "p3", V2))
        value, disagreements, selected = resolve_value(obs)
        assert value == V1
        assert len(disagreements) == 1
        assert disagreements[0].provider_id == "p3"

    def test_no_observation_discarded(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V2), _obs("o3", "p3", V2))
        value, disagreements, selected = resolve_value(obs)
        assert value == V2  # p2 and p3 both support V2, majority
        assert len(disagreements) == 1
        assert disagreements[0].observation_id == "o1"

    def test_disagreement_preserves_reported_value(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1), _obs("o3", "p3", V2))
        _, disagreements, _ = resolve_value(obs)
        assert disagreements[0].reported_value == V2

    def test_deterministic_tie_break_not_provider_identity(self):
        """A 1-1 tie must break on canonical value content, not provider id."""
        obs_a_first = (_obs("o1", "z-provider", V1), _obs("o2", "a-provider", V2))
        obs_b_first = (_obs("o1", "a-provider", V2), _obs("o2", "z-provider", V1))
        value_a, _, _ = resolve_value(obs_a_first)
        value_b, _, _ = resolve_value(obs_b_first)
        assert value_a == value_b  # same tie-break outcome regardless of which provider is which

    def test_order_independent_result(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1), _obs("o3", "p3", V2))
        forward = resolve_value(obs)
        backward = resolve_value(tuple(reversed(obs)))
        assert forward[0] == backward[0]
        assert set(d.observation_id for d in forward[1]) == \
            set(d.observation_id for d in backward[1])

    def test_selected_provider_supports_selected_value(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        value, _, selected = resolve_value(obs)
        supporting = {o.provider_id for o in obs if o.value == value}
        assert selected in supporting

    def test_raises_on_inconsistent_group(self):
        obs = (_obs("o1", "p1", V1, otype="a"), _obs("o2", "p2", V1, otype="b"))
        with pytest.raises(InconsistentGroupError):
            resolve_value(obs)


class TestComputeConfidence:
    def test_single_provider_confidence(self):
        obs = (_obs("o1", "p1", V1),)
        conf = compute_confidence(obs, frozenset({"p1"}))
        assert conf == 0.5

    def test_two_agreeing_providers_full_corroboration(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        conf = compute_confidence(obs, frozenset({"p1", "p2"}))
        assert conf == 1.0

    def test_partial_agreement_lower_confidence(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1), _obs("o3", "p3", V2))
        conf = compute_confidence(obs, frozenset({"p1", "p2"}))
        assert conf == pytest.approx(2 / 3)

    def test_confidence_always_in_unit_interval(self):
        for n_agree in range(1, 5):
            for n_total in range(n_agree, n_agree + 5):
                agree_ids = frozenset(f"p{i}" for i in range(n_agree))
                obs = tuple(_obs(f"o{i}", f"p{i}", V1) for i in range(n_total))
                conf = compute_confidence(obs, agree_ids)
                assert 0.0 <= conf <= 1.0

    def test_deterministic(self):
        obs = (_obs("o1", "p1", V1), _obs("o2", "p2", V1))
        a = compute_confidence(obs, frozenset({"p1", "p2"}))
        b = compute_confidence(obs, frozenset({"p1", "p2"}))
        assert a == b


class TestFactIdentity:
    def test_same_input_same_id(self):
        a = fact_identity("market_price", T, V1)
        b = fact_identity("market_price", T, V1)
        assert a == b

    def test_different_type_different_id(self):
        assert fact_identity("a", T, V1) != fact_identity("b", T, V1)

    def test_different_time_different_id(self):
        assert fact_identity("market_price", T, V1) != fact_identity("market_price", T2, V1)

    def test_different_value_different_id(self):
        assert fact_identity("market_price", T, V1) != fact_identity("market_price", T, V2)

    def test_output_is_lowercase_hex_sha256(self):
        fid = fact_identity("market_price", T, V1)
        assert len(fid) == 64
        assert fid == fid.lower()
        int(fid, 16)
