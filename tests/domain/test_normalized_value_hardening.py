"""ASA-CORE-002: normalized-value and runtime-type hardening tests."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain import DomainInvariantError, is_normalized_value
from domain.canonical_fact import CanonicalFact
from domain.observation import Observation
from domain.outcome_metrics import ExpectedOutcomeMetrics
from domain.provenance import Provenance
from domain.references import Confidence

AWARE = datetime(2026, 7, 21, tzinfo=timezone.utc)

NAN = float("nan")
INF = float("inf")


def _metrics(**overrides):
    kwargs = dict(
        expected_return=Decimal("0.10"),
        maximum_loss=Decimal("-100"),
        capital_required=Decimal("1000"),
        time_horizon_days=30,
    )
    kwargs.update(overrides)
    return ExpectedOutcomeMetrics(**kwargs)


def _observation(value):
    return Observation(
        observation_id="obs-1", observation_type="t", provider_id="p",
        value=value, effective_time=AWARE, recorded_time=AWARE,
    )


# ---------------------------------------------------------------------------
# Non-finite numerics rejected recursively
# ---------------------------------------------------------------------------

class TestNonFiniteRejection:
    @pytest.mark.parametrize("bad", [
        NAN, INF, -INF,
        Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"),
    ])
    def test_scalar_non_finite_rejected(self, bad):
        assert not is_normalized_value(bad)

    @pytest.mark.parametrize("bad", [
        (1.0, NAN),
        (("k", INF),),
        ((("nested", (Decimal("NaN"),)),),),
        (("k", (1, -INF)),),
    ])
    def test_nested_non_finite_rejected(self, bad):
        assert not is_normalized_value(bad)

    def test_observation_rejects_nan_value(self):
        with pytest.raises(DomainInvariantError):
            _observation(NAN)

    def test_observation_rejects_nested_decimal_infinity(self):
        with pytest.raises(DomainInvariantError):
            _observation((("price", Decimal("Infinity")),))

    def test_finite_values_still_accepted(self):
        assert is_normalized_value(1.5)
        assert is_normalized_value(Decimal("1.5"))


# ---------------------------------------------------------------------------
# Mapping key uniqueness
# ---------------------------------------------------------------------------

class TestMappingKeyUniqueness:
    def test_duplicate_keys_rejected(self):
        assert not is_normalized_value((("k", 1), ("k", 2)))

    def test_duplicate_keys_rejected_nested(self):
        assert not is_normalized_value((("outer", (("k", 1), ("k", 2))),))

    def test_observation_rejects_duplicate_mapping_keys(self):
        with pytest.raises(DomainInvariantError):
            _observation((("price", 1), ("price", 2)))

    def test_unique_keys_accepted(self):
        assert is_normalized_value((("a", 1), ("b", 2)))


# ---------------------------------------------------------------------------
# Runtime primitive types
# ---------------------------------------------------------------------------

class TestRuntimeTypes:
    def test_bool_rejected_as_version(self):
        with pytest.raises(DomainInvariantError):
            CanonicalFact(
                fact_id="f", version=True, fact_type="t", value=1,
                confidence=Confidence(score=0.5),
                provenance=Provenance(
                    contributing_observation_ids=(), contributing_provider_ids=(),
                    selected_provider_id=None, disagreements=(), reconciled_at=AWARE),
                effective_time=AWARE, created_time=AWARE)

    def test_non_integer_version_rejected(self):
        with pytest.raises(DomainInvariantError):
            CanonicalFact(
                fact_id="f", version=1.0, fact_type="t", value=1,
                confidence=Confidence(score=0.5),
                provenance=Provenance(
                    contributing_observation_ids=(), contributing_provider_ids=(),
                    selected_provider_id=None, disagreements=(), reconciled_at=AWARE),
                effective_time=AWARE, created_time=AWARE)

    def test_bool_rejected_as_time_horizon(self):
        with pytest.raises(DomainInvariantError):
            _metrics(time_horizon_days=True)

    def test_non_integer_time_horizon_rejected(self):
        with pytest.raises(DomainInvariantError):
            _metrics(time_horizon_days=30.0)

    @pytest.mark.parametrize("field_name", ["expected_return", "maximum_loss",
                                             "capital_required"])
    def test_float_financial_metric_rejected(self, field_name):
        with pytest.raises(DomainInvariantError):
            _metrics(**{field_name: 0.0 if field_name != "maximum_loss" else -1.0})

    def test_int_financial_metric_rejected(self):
        with pytest.raises(DomainInvariantError):
            _metrics(capital_required=1000)

    def test_non_finite_decimal_metric_rejected(self):
        with pytest.raises(DomainInvariantError):
            _metrics(expected_return=Decimal("NaN"))

    def test_optional_metrics_must_be_decimal_when_present(self):
        with pytest.raises(DomainInvariantError):
            _metrics(probability_of_profit=0.5)

    def test_time_horizon_is_mandatory(self):
        with pytest.raises(DomainInvariantError):
            _metrics(time_horizon_days=None)

    def test_valid_metrics_accepted(self):
        m = _metrics(maximum_gain=Decimal("500"),
                     probability_of_profit=Decimal("0.6"))
        assert m.time_horizon_days == 30
