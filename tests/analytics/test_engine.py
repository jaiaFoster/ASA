from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from analytics.engine import compute_feature
from analytics.registry import AnalyticsFeatureDefinition
from domain import EvidenceKind, EvidenceReference, MarketCapability

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "analytics:test-evidence"),)


@dataclass(frozen=True)
class FixedClock:
    fixed_at: datetime = AS_OF

    def now(self) -> datetime:
        return self.fixed_at


def _double(inputs: Mapping[str, object]) -> Decimal:
    """A synthetic, deliberately non-financial computation -- ANALYTICS-001
    proves the framework's mechanics, not any real formula (that's
    ANALYTICS-002's job).
    """
    return Decimal(str(inputs["value"])) * 2


def _raises(inputs: Mapping[str, object]) -> Decimal:
    raise ValueError("insufficient input for this synthetic computation")


_DEFINITION = AnalyticsFeatureDefinition(
    "synthetic_double", "1.0.0", "Doubles a value; test-only.", (MarketCapability.OPTION_CHAIN_V1,)
)


class TestComputeFeature:
    def test_wraps_the_computation_result_canonically(self) -> None:
        result = compute_feature(
            _DEFINITION,
            _double,
            {"value": "21"},
            subject_identity="figi:BBG000B9XRY4",
            clock=FixedClock(),
            parameters=(("value", "21"),),
            input_provenance=EVIDENCE,
        )
        assert result.feature_id == "synthetic_double"
        assert result.feature_version == "1.0.0"
        assert result.value == Decimal("42")
        assert result.as_of == AS_OF
        assert result.parameters == (("value", "21"),)
        assert result.input_provenance == EVIDENCE

    def test_defaults_are_empty(self) -> None:
        result = compute_feature(
            _DEFINITION,
            _double,
            {"value": "1"},
            subject_identity="figi:BBG000B9XRY4",
            clock=FixedClock(),
        )
        assert result.parameters == ()
        assert result.input_provenance == ()

    def test_computation_exceptions_propagate_uncaught(self) -> None:
        """The engine performs no isolation -- unlike a screening strategy
        run, a feature computation is a synchronous helper call within a
        larger, already-isolated caller.
        """
        with pytest.raises(ValueError, match="insufficient input"):
            compute_feature(
                _DEFINITION,
                _raises,
                {},
                subject_identity="figi:BBG000B9XRY4",
                clock=FixedClock(),
            )

    def test_is_deterministic_for_identical_inputs_and_clock(self) -> None:
        first = compute_feature(
            _DEFINITION, _double, {"value": "5"}, subject_identity="figi:x", clock=FixedClock()
        )
        second = compute_feature(
            _DEFINITION, _double, {"value": "5"}, subject_identity="figi:x", clock=FixedClock()
        )
        assert first == second
