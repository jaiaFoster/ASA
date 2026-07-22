from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from analytics.features import DerivedFeatureResult
from domain import EvidenceKind, EvidenceReference

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "analytics:test-evidence"),)


def _result(**overrides: object) -> DerivedFeatureResult:
    fields: dict[str, object] = {
        "feature_id": "days_to_expiration",
        "feature_version": "1.0.0",
        "subject_identity": "figi:BBG000B9XRY4",
        "as_of": AS_OF,
        "value": Decimal("16"),
        "parameters": (("expiration", "2026-08-07"),),
        "input_provenance": EVIDENCE,
    }
    fields.update(overrides)
    return DerivedFeatureResult(**fields)  # type: ignore[arg-type]


class TestDerivedFeatureResultInvariants:
    def test_valid_result_constructs(self) -> None:
        result = _result()
        assert result.value == Decimal("16")

    @pytest.mark.parametrize(
        "field", ["feature_id", "feature_version", "subject_identity"]
    )
    def test_empty_identity_field_rejected(self, field: str) -> None:
        with pytest.raises(ValueError, match="normalized text"):
            _result(**{field: ""})

    def test_naive_as_of_rejected(self) -> None:
        with pytest.raises(ValueError):
            _result(as_of=datetime(2026, 7, 22, 16, 0))

    def test_duplicate_parameter_keys_rejected(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            _result(parameters=(("expiration", "2026-08-07"), ("expiration", "2026-09-18")))

    def test_unnormalized_parameter_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="normalized text"):
            _result(parameters=((" expiration ", "2026-08-07"),))

    def test_unnormalized_parameter_value_rejected(self) -> None:
        with pytest.raises(ValueError, match="normalized text"):
            _result(parameters=(("expiration", " 2026-08-07 "),))

    def test_empty_parameters_is_allowed(self) -> None:
        result = _result(parameters=())
        assert result.parameters == ()

    def test_empty_provenance_is_allowed(self) -> None:
        result = _result(input_provenance=())
        assert result.input_provenance == ()
