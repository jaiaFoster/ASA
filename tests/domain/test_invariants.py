"""ASA-CORE-001A: primitive invariant enforcement tests.

Exit criteria covered:
- no domain entity can contain a mutable nested value
- confidence/probability cannot fall outside [0, 1]
- versions must be positive
- all persisted timestamps must be timezone-aware
- an Opportunity cannot carry an entirely empty comparison payload
- every financial metric has an explicit unit and interpretation
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain import (
    CanonicalFact,
    Confidence,
    DomainInvariantError,
    EvidenceKind,
    EvidenceReference,
    ExpectedOutcomeMetrics,
    GuardrailOutcome,
    Indicator,
    Observation,
    Opportunity,
    Provenance,
    ProviderDisagreement,
    RecommendationState,
    is_normalized_value,
)

AWARE = datetime(2026, 7, 21, tzinfo=timezone.utc)
NAIVE = datetime(2026, 7, 21)


def _provenance(**overrides):
    kwargs = dict(
        contributing_observation_ids=("obs-1",),
        contributing_provider_ids=("prov-a",),
        selected_provider_id="prov-a",
        disagreements=(),
        reconciled_at=AWARE,
    )
    kwargs.update(overrides)
    return Provenance(**kwargs)


def _metrics(**overrides):
    kwargs = dict(
        expected_return=Decimal("0.10"),
        maximum_loss=Decimal("-100"),
        capital_required=Decimal("1000"),
        time_horizon_days=30,
    )
    kwargs.update(overrides)
    return ExpectedOutcomeMetrics(**kwargs)


def _observation(**overrides):
    kwargs = dict(
        observation_id="obs-1", observation_type="price", provider_id="prov-a",
        value=100.0, effective_time=AWARE, recorded_time=AWARE,
    )
    kwargs.update(overrides)
    return Observation(**kwargs)


def _fact(**overrides):
    kwargs = dict(
        fact_id="fact-1", version=1, fact_type="price", value=100.0,
        confidence=Confidence(score=0.9), provenance=_provenance(),
        effective_time=AWARE, created_time=AWARE,
    )
    kwargs.update(overrides)
    return CanonicalFact(**kwargs)


def _indicator(**overrides):
    kwargs = dict(
        indicator_id="ind-1", version=1, indicator_type="latest_price",
        logic_version="1.0.0", value=1.5,
        computed_from=(), effective_time=AWARE, created_time=AWARE,
    )
    kwargs.update(overrides)
    return Indicator(**kwargs)


def _opportunity(**overrides):
    kwargs = dict(
        opportunity_id="opp-1", version=1,
        strategy_id="strat-1", strategy_version="1.0.0",
        supporting_indicators=(), evidence=(), assumptions=(),
        evidence_confidence=Confidence(score=0.5),
        expected_outcome_metrics=_metrics(),
        state=RecommendationState.DISCOVERED,
        effective_time=AWARE, created_time=AWARE,
    )
    kwargs.update(overrides)
    return Opportunity(**kwargs)


# ---------------------------------------------------------------------------
# Normalized value contract — no mutable nested values
# ---------------------------------------------------------------------------

class TestNormalizedValueContract:
    @pytest.mark.parametrize("good", [
        None, True, 1, 1.5, Decimal("1.5"), "text", AWARE,
        (1, 2, 3),
        (("bid", 1.0), ("ask", 1.1)),
        ((("nested", (1, 2)),),),
    ])
    def test_accepts_normalized(self, good):
        assert is_normalized_value(good)

    @pytest.mark.parametrize("bad", [
        [1, 2], {"a": 1}, {1, 2}, bytearray(b"x"), (1, [2]), (("k", [1]),), NAIVE,
    ])
    def test_rejects_mutable_or_naive(self, bad):
        assert not is_normalized_value(bad)

    def test_observation_rejects_mutable_value(self):
        with pytest.raises(DomainInvariantError):
            _observation(value=[1, 2, 3])

    def test_observation_rejects_dict_value(self):
        with pytest.raises(DomainInvariantError):
            _observation(value={"price": 100})

    def test_canonical_fact_rejects_mutable_value(self):
        with pytest.raises(DomainInvariantError):
            _fact(value={"resolved": 100})

    def test_indicator_rejects_mutable_value(self):
        with pytest.raises(DomainInvariantError):
            _indicator(value=[1.5])

    def test_disagreement_rejects_mutable_value(self):
        with pytest.raises(DomainInvariantError):
            ProviderDisagreement(provider_id="p", observation_id="o",
                                 reported_value={"v": 1})

    def test_nested_tuple_mapping_accepted(self):
        obs = _observation(value=(("bid", Decimal("1.0")), ("ask", Decimal("1.1"))))
        assert obs.value[0] == ("bid", Decimal("1.0"))


# ---------------------------------------------------------------------------
# Range invariants
# ---------------------------------------------------------------------------

class TestRangeInvariants:
    @pytest.mark.parametrize("score", [-0.01, 1.01, 2.0])
    def test_confidence_out_of_range_rejected(self, score):
        with pytest.raises(DomainInvariantError):
            Confidence(score=score)

    @pytest.mark.parametrize("score", [0.0, 0.5, 1.0])
    def test_confidence_in_range_accepted(self, score):
        assert Confidence(score=score).score == score

    @pytest.mark.parametrize("p", [Decimal("-0.1"), Decimal("1.1")])
    def test_probability_out_of_range_rejected(self, p):
        with pytest.raises(DomainInvariantError):
            _metrics(probability_of_profit=p)

    def test_probability_bounds_accepted(self):
        assert _metrics(probability_of_profit=Decimal("0")).probability_of_profit == 0
        assert _metrics(probability_of_profit=Decimal("1")).probability_of_profit == 1


# ---------------------------------------------------------------------------
# Version invariants
# ---------------------------------------------------------------------------

class TestVersionInvariants:
    @pytest.mark.parametrize("bad", [0, -1])
    def test_fact_version_must_be_positive(self, bad):
        with pytest.raises(DomainInvariantError):
            _fact(version=bad)

    @pytest.mark.parametrize("bad", [0, -1])
    def test_indicator_version_must_be_positive(self, bad):
        with pytest.raises(DomainInvariantError):
            _indicator(version=bad)

    @pytest.mark.parametrize("bad", [0, -1])
    def test_opportunity_version_must_be_positive(self, bad):
        with pytest.raises(DomainInvariantError):
            _opportunity(version=bad)

    def test_evidence_reference_version_must_be_positive(self):
        with pytest.raises(DomainInvariantError):
            EvidenceReference(kind=EvidenceKind.CANONICAL_FACT,
                              referenced_id="f", version=0)

    def test_evidence_reference_none_version_allowed(self):
        ref = EvidenceReference(kind=EvidenceKind.OBSERVATION, referenced_id="o")
        assert ref.version is None


# ---------------------------------------------------------------------------
# Timezone-aware timestamps
# ---------------------------------------------------------------------------

class TestTimezoneInvariants:
    def test_observation_rejects_naive_effective(self):
        with pytest.raises(DomainInvariantError):
            _observation(effective_time=NAIVE)

    def test_observation_rejects_naive_recorded(self):
        with pytest.raises(DomainInvariantError):
            _observation(recorded_time=NAIVE)

    def test_fact_rejects_naive_timestamps(self):
        with pytest.raises(DomainInvariantError):
            _fact(created_time=NAIVE)

    def test_indicator_rejects_naive_timestamps(self):
        with pytest.raises(DomainInvariantError):
            _indicator(effective_time=NAIVE)

    def test_opportunity_rejects_naive_timestamps(self):
        with pytest.raises(DomainInvariantError):
            _opportunity(created_time=NAIVE)

    def test_provenance_rejects_naive_reconciled_at(self):
        with pytest.raises(DomainInvariantError):
            _provenance(reconciled_at=NAIVE)

    def test_guardrail_outcome_rejects_naive_evaluated_at(self):
        with pytest.raises(DomainInvariantError):
            GuardrailOutcome(guardrail_id="g", guardrail_version="1", passed=True,
                             reason="ok", evidence=(), evaluated_at=NAIVE)


# ---------------------------------------------------------------------------
# Expected Outcome Metrics: mandatory payload and unit semantics
# ---------------------------------------------------------------------------

class TestOutcomeMetricsContract:
    @pytest.mark.parametrize("missing", ["expected_return", "maximum_loss",
                                          "capital_required", "time_horizon_days"])
    def test_mandatory_metrics_cannot_be_none(self, missing):
        with pytest.raises(DomainInvariantError):
            _metrics(**{missing: None})

    def test_optional_metrics_default_to_none(self):
        m = _metrics()
        assert m.maximum_gain is None
        assert m.probability_of_profit is None

    def test_maximum_loss_must_be_non_positive(self):
        with pytest.raises(DomainInvariantError):
            _metrics(maximum_loss=Decimal("50"))

    def test_zero_maximum_loss_allowed(self):
        assert _metrics(maximum_loss=Decimal("0")).maximum_loss == 0

    def test_capital_required_must_be_non_negative(self):
        with pytest.raises(DomainInvariantError):
            _metrics(capital_required=Decimal("-1"))

    def test_maximum_gain_must_be_non_negative_when_present(self):
        with pytest.raises(DomainInvariantError):
            _metrics(maximum_gain=Decimal("-1"))

    def test_time_horizon_must_be_positive(self):
        with pytest.raises(DomainInvariantError):
            _metrics(time_horizon_days=0)

    def test_opportunity_cannot_have_empty_comparison_payload(self):
        """Mandatory metrics guarantee a non-empty payload on every Opportunity."""
        with pytest.raises(DomainInvariantError):
            _opportunity(expected_outcome_metrics=ExpectedOutcomeMetrics(
                expected_return=None, maximum_loss=None, capital_required=None,
                time_horizon_days=None))

    def test_units_documented_in_docstring(self):
        doc = ExpectedOutcomeMetrics.__doc__
        assert "USD" in doc and "[0, 1]" in doc and "decimal fraction" in doc
