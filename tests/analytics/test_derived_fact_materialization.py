"""SPRINT-014 S14-PR-04: derived-fact materialization tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from analytics.derived_fact_materialization import derived_fact_id, materialize_derived_fact
from analytics.derived_facts import DERIVED_FACT_REGISTRY, REALIZED_VOLATILITY
from analytics.errors import UnknownFeatureIdError
from analytics.features import DerivedFact, DerivedFactQualityStatus
from domain import EvidenceKind, EvidenceReference

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "obs-1"),)


def test_derived_fact_id_is_deterministic_for_the_same_inputs() -> None:
    first = derived_fact_id(REALIZED_VOLATILITY, "AAPL", "digest-1")
    second = derived_fact_id(REALIZED_VOLATILITY, "AAPL", "digest-1")
    assert first == second


def test_derived_fact_id_differs_by_subject_and_by_snapshot() -> None:
    base = derived_fact_id(REALIZED_VOLATILITY, "AAPL", "digest-1")
    different_subject = derived_fact_id(REALIZED_VOLATILITY, "MSFT", "digest-1")
    different_snapshot = derived_fact_id(REALIZED_VOLATILITY, "AAPL", "digest-2")
    assert len({base, different_subject, different_snapshot}) == 3


def test_materializes_a_derived_fact_using_the_registered_formula_version() -> None:
    fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        REALIZED_VOLATILITY,
        "AAPL",
        "digest-1",
        value=Decimal("0.42"),
        unit="annualized_decimal",
        effective_time=NOW,
        input_evidence=EVIDENCE,
        quality_status=DerivedFactQualityStatus.VALID,
    )
    assert isinstance(fact, DerivedFact)
    assert fact.derived_fact_id == derived_fact_id(REALIZED_VOLATILITY, "AAPL", "digest-1")
    definition = DERIVED_FACT_REGISTRY.get(REALIZED_VOLATILITY)
    assert fact.formula_version == definition.feature_version
    assert fact.value == Decimal("0.42")


def test_the_same_feature_subject_and_snapshot_always_yields_the_same_id() -> None:
    # This is what "compute once per snapshot and parameter set" (I-08)
    # means in practice: computing the same feature twice for the same
    # (subject, snapshot) produces identical identity, so a caller can
    # detect "already materialized" before recomputing.
    first = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        REALIZED_VOLATILITY,
        "AAPL",
        "digest-1",
        value=Decimal("0.42"),
        unit="annualized_decimal",
        effective_time=NOW,
        input_evidence=EVIDENCE,
        quality_status=DerivedFactQualityStatus.VALID,
    )
    second = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        REALIZED_VOLATILITY,
        "AAPL",
        "digest-1",
        value=Decimal("0.42"),
        unit="annualized_decimal",
        effective_time=NOW,
        input_evidence=EVIDENCE,
        quality_status=DerivedFactQualityStatus.VALID,
    )
    assert first.derived_fact_id == second.derived_fact_id
    assert first.identity == second.identity


def test_omitting_parameters_reproduces_the_original_three_argument_id() -> None:
    # I-07's parameters component is backward compatible: the default
    # (empty parameters) must still produce the exact same ID the
    # original three-argument derived_fact_id shape always produced.
    assert derived_fact_id(REALIZED_VOLATILITY, "AAPL", "digest-1") == derived_fact_id(
        REALIZED_VOLATILITY, "AAPL", "digest-1", parameters=()
    )


def test_different_parameters_produce_different_ids_for_the_same_subject_and_snapshot() -> None:
    # The exact collision this closes: two different selections (e.g. two
    # different contracts) within the same subject/snapshot must never
    # reuse one derived_fact_id for two different values.
    front_selected = derived_fact_id(
        REALIZED_VOLATILITY, "AAPL", "digest-1", parameters=(("contract_id", "front-123"),)
    )
    back_selected = derived_fact_id(
        REALIZED_VOLATILITY, "AAPL", "digest-1", parameters=(("contract_id", "back-456"),)
    )
    unparameterized = derived_fact_id(REALIZED_VOLATILITY, "AAPL", "digest-1")
    assert len({front_selected, back_selected, unparameterized}) == 3


def test_parameter_identity_is_order_independent() -> None:
    forward = derived_fact_id(
        REALIZED_VOLATILITY,
        "AAPL",
        "digest-1",
        parameters=(("a", "1"), ("b", "2")),
    )
    backward = derived_fact_id(
        REALIZED_VOLATILITY,
        "AAPL",
        "digest-1",
        parameters=(("b", "2"), ("a", "1")),
    )
    assert forward == backward


def test_materialize_derived_fact_accepts_and_forwards_parameters() -> None:
    fact = materialize_derived_fact(
        DERIVED_FACT_REGISTRY,
        REALIZED_VOLATILITY,
        "AAPL",
        "digest-1",
        value=Decimal("0.42"),
        unit="annualized_decimal",
        effective_time=NOW,
        input_evidence=EVIDENCE,
        quality_status=DerivedFactQualityStatus.VALID,
        parameters=(("contract_id", "front-123"),),
    )
    assert fact.derived_fact_id == derived_fact_id(
        REALIZED_VOLATILITY, "AAPL", "digest-1", parameters=(("contract_id", "front-123"),)
    )


def test_an_unregistered_feature_id_is_rejected() -> None:
    with pytest.raises(UnknownFeatureIdError):
        materialize_derived_fact(
            DERIVED_FACT_REGISTRY,
            "not_a_registered_feature",
            "AAPL",
            "digest-1",
            value=Decimal("1"),
            unit="unit",
            effective_time=NOW,
            input_evidence=EVIDENCE,
            quality_status=DerivedFactQualityStatus.VALID,
        )
