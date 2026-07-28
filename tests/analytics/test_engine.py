from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from analytics.engine import compute_feature
from analytics.features import DerivedFactQualityStatus
from analytics.registry import AnalyticsFeatureDefinition
from domain import EvidenceKind, EvidenceReference, MarketCapability

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "analytics:test-evidence"),)


@dataclass(frozen=True)
class FixedClock:
    def now(self) -> datetime:
        return AS_OF


def _double(inputs: Mapping[str, object]) -> Decimal:
    return Decimal(str(inputs["value"])) * 2


def _raises(inputs: Mapping[str, object]) -> Decimal:
    raise ValueError("insufficient input")


DEFINITION = AnalyticsFeatureDefinition(
    "synthetic_double",
    "1.0.0",
    "Doubles a value; test-only.",
    (MarketCapability.OPTION_CHAIN_V1,),
)


def test_engine_wraps_named_computation_with_provenance() -> None:
    result = compute_feature(
        DEFINITION,
        _double,
        {"value": "21"},
        clock=FixedClock(),
        unit="ratio",
        input_evidence=EVIDENCE,
    )
    assert result.derived_fact_id == "synthetic_double"
    assert result.formula_version == "1.0.0"
    assert result.value == Decimal("42")
    assert result.effective_time == AS_OF
    assert result.quality_status is DerivedFactQualityStatus.VALID
    assert result.input_evidence == EVIDENCE


def test_computation_exceptions_propagate() -> None:
    with pytest.raises(ValueError, match="insufficient input"):
        compute_feature(DEFINITION, _raises, {}, clock=FixedClock(), unit="ratio")


def test_identical_inputs_and_clock_replay_identically() -> None:
    first = compute_feature(DEFINITION, _double, {"value": "5"}, clock=FixedClock(), unit="ratio")
    second = compute_feature(DEFINITION, _double, {"value": "5"}, clock=FixedClock(), unit="ratio")
    assert first == second
