"""ASA-CORE-001: immutable domain model tests.

Verifies:
- every domain object is a frozen dataclass (immutable, raises on mutation)
- identity, version, and timestamp fields exist where the ticket requires
- provenance is represented in all required entities
- ExpectedOutcomeMetrics exists and no Strategy-confidence field exists
- no business logic: domain classes define no public methods of their own
"""
from __future__ import annotations

import dataclasses
import inspect
from datetime import datetime, timezone
from decimal import Decimal

import pytest

import domain
from domain import (
    CanonicalFact,
    Confidence,
    EvidenceKind,
    EvidenceReference,
    ExpectedOutcomeMetrics,
    GuardrailOutcome,
    Indicator,
    Observation,
    Opportunity,
    Provenance,
    Provider,
    ProviderDisagreement,
    RecommendationState,
)
from tests.instrument_helpers import TEST_INSTRUMENT

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)

DOMAIN_CLASSES = [
    CanonicalFact,
    Confidence,
    EvidenceReference,
    ExpectedOutcomeMetrics,
    GuardrailOutcome,
    Indicator,
    Observation,
    Opportunity,
    Provenance,
    Provider,
    ProviderDisagreement,
]


def _sample_provenance() -> Provenance:
    return Provenance(
        contributing_observation_ids=("obs-1", "obs-2"),
        contributing_provider_ids=("prov-a", "prov-b"),
        selected_provider_id="prov-a",
        disagreements=(
            ProviderDisagreement(provider_id="prov-b", observation_id="obs-2",
                                 reported_value=101.5),
        ),
        reconciled_at=NOW,
        reconciliation_metadata=(("priority_winner", "prov-a"),),
    )


def _sample_fact() -> CanonicalFact:
    return CanonicalFact(
        fact_id="fact-1", version=1, fact_type="price", value=100.0,
        confidence=Confidence(score=0.9), provenance=_sample_provenance(),
        effective_time=NOW, created_time=NOW,
    )


def _sample_metrics() -> ExpectedOutcomeMetrics:
    return ExpectedOutcomeMetrics(
        expected_return=Decimal("0.12"), maximum_gain=Decimal("500"),
        maximum_loss=Decimal("-200"), capital_required=Decimal("2000"),
        probability_of_profit=Decimal("0.65"), time_horizon_days=30,
    )


def _sample_opportunity() -> Opportunity:
    ref = EvidenceReference(kind=EvidenceKind.CANONICAL_FACT,
                            referenced_id="fact-1", version=1)
    return Opportunity(
        opportunity_id="opp-1", version=1,
        strategy_id="strat-1", strategy_version="1.0.0",
        instrument=TEST_INSTRUMENT,
        supporting_indicators=(EvidenceReference(
            kind=EvidenceKind.INDICATOR, referenced_id="ind-1", version=3),),
        evidence=(ref,), assumptions=("normal market conditions",),
        evidence_confidence=Confidence(score=0.8),
        expected_outcome_metrics=_sample_metrics(),
        state=RecommendationState.DISCOVERED,
        effective_time=NOW, created_time=NOW,
        guardrail_outcomes=(GuardrailOutcome(
            guardrail_id="gr-1", guardrail_version="1.0.0", passed=True,
            reason="DTE above minimum", evidence=(ref,), evaluated_at=NOW),),
    )


SAMPLES = {
    Provider: lambda: Provider(provider_id="prov-a", name="Alpha"),
    Confidence: lambda: Confidence(score=0.5),
    EvidenceReference: lambda: EvidenceReference(
        kind=EvidenceKind.OBSERVATION, referenced_id="obs-1"),
    ProviderDisagreement: lambda: ProviderDisagreement(
        provider_id="p", observation_id="o", reported_value=1),
    Provenance: _sample_provenance,
    Observation: lambda: Observation(
        observation_id="obs-1", observation_type="price", provider_id="prov-a",
        value=100.0, effective_time=NOW, recorded_time=NOW),
    CanonicalFact: _sample_fact,
    Indicator: lambda: Indicator(
        indicator_id="ind-1", version=3, indicator_type="latest_price",
        logic_version="2.0.0", value=1.5,
        computed_from=(EvidenceReference(
            kind=EvidenceKind.CANONICAL_FACT, referenced_id="fact-1", version=1),),
        effective_time=NOW, created_time=NOW),
    ExpectedOutcomeMetrics: _sample_metrics,
    GuardrailOutcome: lambda: GuardrailOutcome(
        guardrail_id="gr-1", guardrail_version="1.0.0", passed=False,
        reason="capital limit exceeded", evidence=(), evaluated_at=NOW),
    Opportunity: _sample_opportunity,
}


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", DOMAIN_CLASSES, ids=lambda c: c.__name__)
def test_is_frozen_dataclass(cls):
    assert dataclasses.is_dataclass(cls), f"{cls.__name__} is not a dataclass"
    assert cls.__dataclass_params__.frozen, f"{cls.__name__} is not frozen"


@pytest.mark.parametrize("cls", DOMAIN_CLASSES, ids=lambda c: c.__name__)
def test_mutation_raises(cls):
    instance = SAMPLES[cls]()
    first_field = dataclasses.fields(cls)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, first_field, "mutated")


@pytest.mark.parametrize("cls", DOMAIN_CLASSES, ids=lambda c: c.__name__)
def test_collection_fields_are_tuples_not_lists(cls):
    """Collection-typed fields must be tuples so instances are deeply immutable."""
    instance = SAMPLES[cls]()
    for f in dataclasses.fields(cls):
        value = getattr(instance, f.name)
        assert not isinstance(value, (list, dict, set)), (
            f"{cls.__name__}.{f.name} holds a mutable collection"
        )


# ---------------------------------------------------------------------------
# Identity, versioning, timestamps
# ---------------------------------------------------------------------------

VERSIONED = {CanonicalFact: "version", Indicator: "version", Opportunity: "version"}
TIMESTAMPED = {
    Observation: ("effective_time", "recorded_time"),
    CanonicalFact: ("effective_time", "created_time"),
    Indicator: ("effective_time", "created_time"),
    Opportunity: ("effective_time", "created_time"),
}
IDENTIFIED = {
    Provider: "provider_id",
    Observation: "observation_id",
    CanonicalFact: "fact_id",
    Indicator: "indicator_id",
    Opportunity: "opportunity_id",
    GuardrailOutcome: "guardrail_id",
}


@pytest.mark.parametrize("cls,field_name", VERSIONED.items(), ids=lambda x: getattr(x, "__name__", x))
def test_versioned_entities_have_version_field(cls, field_name):
    assert field_name in {f.name for f in dataclasses.fields(cls)}


@pytest.mark.parametrize("cls,fields", TIMESTAMPED.items(), ids=lambda x: getattr(x, "__name__", x))
def test_timestamps_present(cls, fields):
    names = {f.name for f in dataclasses.fields(cls)}
    for fname in fields:
        assert fname in names, f"{cls.__name__} missing timestamp field {fname}"


@pytest.mark.parametrize("cls,field_name", IDENTIFIED.items(), ids=lambda x: getattr(x, "__name__", x))
def test_identifier_fields_present(cls, field_name):
    assert field_name in {f.name for f in dataclasses.fields(cls)}


def test_indicator_pins_logic_version():
    names = {f.name for f in dataclasses.fields(Indicator)}
    assert "logic_version" in names, "ADR-006: Indicator must pin its calculation-logic version"


def test_indicator_has_indicator_type():
    names = {f.name for f in dataclasses.fields(Indicator)}
    assert "indicator_type" in names, (
        "ASA-CORE-004: Indicator must carry its type, mirroring CanonicalFact.fact_type"
    )


def test_opportunity_pins_strategy_version():
    names = {f.name for f in dataclasses.fields(Opportunity)}
    assert "strategy_version" in names, "ADR-003: Opportunity must pin its Strategy version"


def test_guardrail_outcome_pins_guardrail_version():
    names = {f.name for f in dataclasses.fields(GuardrailOutcome)}
    assert "guardrail_version" in names, "ADR-005: GuardrailOutcome must pin its Guardrail version"


# ---------------------------------------------------------------------------
# Provenance representation (ADR-001 as amended)
# ---------------------------------------------------------------------------

def test_canonical_fact_carries_full_provenance():
    fact = _sample_fact()
    prov = fact.provenance
    assert prov.contributing_provider_ids
    assert prov.selected_provider_id is not None
    assert prov.disagreements is not None
    assert prov.reconciled_at is not None
    assert prov.reconciliation_metadata is not None


def test_indicator_references_fact_versions():
    ind = SAMPLES[Indicator]()
    assert all(r.kind is EvidenceKind.CANONICAL_FACT and r.version is not None
               for r in ind.computed_from)


def test_opportunity_carries_evidence_references():
    opp = _sample_opportunity()
    assert opp.evidence and opp.supporting_indicators


def test_guardrail_outcome_cites_evidence():
    names = {f.name for f in dataclasses.fields(GuardrailOutcome)}
    assert "evidence" in names and "reason" in names


# ---------------------------------------------------------------------------
# ExpectedOutcomeMetrics replaces Strategy Confidence (ADR-003 as amended)
# ---------------------------------------------------------------------------

def test_opportunity_has_expected_outcome_metrics():
    names = {f.name for f in dataclasses.fields(Opportunity)}
    assert "expected_outcome_metrics" in names


def test_no_strategy_confidence_anywhere():
    for cls in DOMAIN_CLASSES:
        names = {f.name for f in dataclasses.fields(cls)}
        assert "strategy_confidence" not in names, (
            f"{cls.__name__} carries strategy_confidence — removed by ADR-003 amendment"
        )


def test_metrics_fields_are_standardized():
    names = {f.name for f in dataclasses.fields(ExpectedOutcomeMetrics)}
    assert {"expected_return", "maximum_gain", "maximum_loss",
            "capital_required", "probability_of_profit",
            "time_horizon_days"} <= names


def test_recommendation_state_covers_lifecycle():
    values = {s.value for s in RecommendationState}
    assert {"discovered", "guardrail_evaluated", "ranked",
            "presented", "rejected"} <= values


# ---------------------------------------------------------------------------
# No business logic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", DOMAIN_CLASSES, ids=lambda c: c.__name__)
def test_no_public_methods_defined(cls):
    """Domain objects are data only — no methods beyond dataclass machinery."""
    own = [
        name for name, member in vars(cls).items()
        if inspect.isfunction(member)
        and not name.startswith("__")
    ]
    assert own == [], f"{cls.__name__} defines business logic methods: {own}"


def test_domain_package_exports_all_required_objects():
    for name in ("Observation", "CanonicalFact", "Indicator", "Opportunity",
                 "Provider", "Provenance", "EvidenceReference",
                 "GuardrailOutcome", "ExpectedOutcomeMetrics",
                 "RecommendationState"):
        assert hasattr(domain, name), f"domain package does not export {name}"
