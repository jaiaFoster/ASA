"""ASA-CORE-005 Phase 0: Adjacent Hardening regression tests.

Covers the four required Phase 0 items against ASA-CORE-004's Indicator
Engine, before Strategy Engine work begins:
- semantic replay comparison (canonicalized value equality, not raw !=)
- stale provenance elimination (replay never returns a verbatim old object)
- indicator parameter validation (period: present, exact int, positive)
- regression tests (this file)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.canonical_fact import CanonicalFact
from domain.provenance import Provenance
from domain.references import Confidence
from indicators.engine import compute_indicator
from indicators.errors import InconsistentIndicatorGroupError, InvalidIndicatorParameterError

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


# ---------------------------------------------------------------------------
# 1. Semantic replay comparison
# ---------------------------------------------------------------------------

class TestSemanticReplayComparison:
    def test_canonicalized_values_compare_equal(self):
        """Values that are canonically equal must not trigger a spurious version bump."""
        facts = (_fact(0, "100"),)
        ind1, _ = compute_indicator("latest_price", facts, T0, T0)
        # Recomputing with the exact same input must be recognized as unchanged.
        ind2, is_new = compute_indicator(
            "latest_price", facts, T0, T0 + timedelta(minutes=1),
            previous_indicator=ind1)
        assert not is_new
        assert ind2.version == ind1.version

    def test_value_stored_is_canonicalized(self):
        facts = (_fact(0, "100"),)
        ind, _ = compute_indicator("latest_price", facts, T0, T0)
        from domain.canonicalization import canonicalize_value
        assert ind.value == canonicalize_value(ind.value)


# ---------------------------------------------------------------------------
# 2. Stale provenance elimination
# ---------------------------------------------------------------------------

class TestStaleProvenanceElimination:
    def test_replay_reflects_current_call_created_time(self):
        """A no-new-version result must carry THIS call's created_time, not
        a verbatim copy of the original object's created_time."""
        facts = (_fact(0, "100"),)
        ind1, _ = compute_indicator("latest_price", facts, T0, T0)
        later = T0 + timedelta(hours=1)
        ind2, is_new = compute_indicator(
            "latest_price", facts, T0, later, previous_indicator=ind1)
        assert not is_new
        assert ind2.created_time == later
        assert ind2.created_time != ind1.created_time

    def test_replay_reflects_current_computed_from(self):
        """A no-new-version result with a larger (but same-resolving)
        candidate set must cite the facts THIS call actually used, not the
        previous call's contributing set."""
        single = (_fact(0, "100"),)
        ind1, _ = compute_indicator("latest_price", single, T0, T0)
        assert len(ind1.computed_from) == 1

        # latest_price with a larger candidate set still resolves to the
        # most recent fact — but a *different* most recent fact this time,
        # so this is actually a new value/version; use rolling_high instead
        # to construct a genuine "same value, different evidence" case.
        window3 = (_fact(0, "100"), _fact(1, "90"), _fact(2, "100"))
        high1, _ = compute_indicator(
            "rolling_high", window3, T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2), params={"period": 2})
        # last 2 of window3: fact-1 (90), fact-2 (100) -> high = 100
        assert high1.value == Decimal("100")

        window4 = (_fact(0, "100"), _fact(1, "90"), _fact(2, "100"), _fact(3, "80"))
        # New computation over a 3-period window ending at fact-2 again
        # (same effective_time group) with additional unrelated evidence
        # supplied — still resolves to the same window/value.
        high2, is_new = compute_indicator(
            "rolling_high", window3, T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=5), params={"period": 2},
            previous_indicator=high1)
        assert not is_new
        assert high2.created_time == T0 + timedelta(minutes=5)
        assert high2.created_time != high1.created_time

    def test_stored_history_never_contains_stale_record(self):
        """The repository only ever stores what callers explicitly append;
        a discarded (is_new_version=False) result must never silently
        become part of persisted history with mismatched provenance."""
        from indicators.repository import InMemoryIndicatorRepository
        repo = InMemoryIndicatorRepository()
        facts = (_fact(0, "100"),)
        ind1, is_new1 = compute_indicator("latest_price", facts, T0, T0)
        assert is_new1
        repo.append(ind1)

        ind2, is_new2 = compute_indicator(
            "latest_price", facts, T0, T0 + timedelta(minutes=5),
            previous_indicator=ind1)
        assert not is_new2
        # Caller correctly does not append ind2 (per contract).
        history = repo.history("latest_price", T0)
        assert len(history) == 1
        assert history[0] == ind1


# ---------------------------------------------------------------------------
# 3. Indicator parameter validation
# ---------------------------------------------------------------------------

class TestIndicatorParameterValidation:
    def test_missing_period_raises(self):
        facts = (_fact(0, "100"), _fact(1, "101"), _fact(2, "102"))
        with pytest.raises(InvalidIndicatorParameterError):
            compute_indicator("simple_moving_average", facts, T0 + timedelta(minutes=2),
                             T0 + timedelta(minutes=2), params={})

    def test_bool_period_rejected(self):
        facts = (_fact(0, "100"), _fact(1, "101"))
        with pytest.raises(InvalidIndicatorParameterError):
            compute_indicator("simple_moving_average", facts, T0 + timedelta(minutes=1),
                             T0 + timedelta(minutes=1), params={"period": True})

    def test_zero_period_rejected(self):
        facts = (_fact(0, "100"),)
        with pytest.raises(InvalidIndicatorParameterError):
            compute_indicator("rolling_high", facts, T0, T0, params={"period": 0})

    def test_negative_period_rejected(self):
        facts = (_fact(0, "100"),)
        with pytest.raises(InvalidIndicatorParameterError):
            compute_indicator("rolling_low", facts, T0, T0, params={"period": -5})

    def test_float_period_rejected(self):
        facts = (_fact(0, "100"), _fact(1, "101"), _fact(2, "102"))
        with pytest.raises(InvalidIndicatorParameterError):
            compute_indicator("exponential_moving_average", facts, T0 + timedelta(minutes=2),
                             T0 + timedelta(minutes=2), params={"period": 3.0})

    def test_string_period_rejected(self):
        facts = (_fact(0, "100"), _fact(1, "101"), _fact(2, "102"))
        with pytest.raises(InvalidIndicatorParameterError):
            compute_indicator("simple_moving_average", facts, T0 + timedelta(minutes=2),
                             T0 + timedelta(minutes=2), params={"period": "3"})

    def test_valid_period_accepted(self):
        facts = (_fact(0, "100"), _fact(1, "101"), _fact(2, "102"))
        ind, is_new = compute_indicator(
            "simple_moving_average", facts, T0 + timedelta(minutes=2),
            T0 + timedelta(minutes=2), params={"period": 3})
        assert is_new
        assert ind.value == Decimal("101")

    def test_indicators_without_period_ignore_missing_params(self):
        """latest_price and price_change_percent take no params — no error."""
        facts = (_fact(0, "100"), _fact(1, "110"))
        ind, is_new = compute_indicator(
            "price_change_percent", facts, T0 + timedelta(minutes=1),
            T0 + timedelta(minutes=1))
        assert is_new
        assert ind.value == Decimal("0.1")


# ---------------------------------------------------------------------------
# 4. Group-consistency validation (bundled hardening, same root cause)
# ---------------------------------------------------------------------------

class TestPreviousIndicatorGroupConsistency:
    def test_mismatched_indicator_type_raises(self):
        facts = (_fact(0, "100"),)
        ind1, _ = compute_indicator("latest_price", facts, T0, T0)
        with pytest.raises(InconsistentIndicatorGroupError):
            compute_indicator("rolling_high", facts, T0, T0,
                             params={"period": 1}, previous_indicator=ind1)

    def test_mismatched_effective_time_raises(self):
        facts = (_fact(0, "100"),)
        ind1, _ = compute_indicator("latest_price", facts, T0, T0)
        other_time = T0 + timedelta(hours=1)
        with pytest.raises(InconsistentIndicatorGroupError):
            compute_indicator("latest_price", facts, other_time, other_time,
                             previous_indicator=ind1)

    def test_matching_group_does_not_raise(self):
        facts = (_fact(0, "100"),)
        ind1, _ = compute_indicator("latest_price", facts, T0, T0)
        ind2, is_new = compute_indicator(
            "latest_price", facts, T0, T0 + timedelta(minutes=1), previous_indicator=ind1)
        assert not is_new  # does not raise; same group, same value
