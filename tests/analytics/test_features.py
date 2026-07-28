from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from analytics.features import (
    DerivedFact,
    DerivedFactQualityStatus,
    DerivedFactSet,
)
from domain import EvidenceKind, EvidenceReference

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "analytics:test-evidence"),)


def _fact(**overrides: object) -> DerivedFact:
    fields: dict[str, object] = {
        "derived_fact_id": "days_to_expiration",
        "value": 16,
        "unit": "calendar_days",
        "formula_version": "1.0.0",
        "effective_time": AS_OF,
        "input_evidence": EVIDENCE,
        "quality_status": DerivedFactQualityStatus.VALID,
    }
    fields.update(overrides)
    return DerivedFact(**fields)  # type: ignore[arg-type]


def test_fact_is_immutable_deterministic_and_complete() -> None:
    fact = _fact()
    assert fact.value == 16
    assert fact.identity == _fact().identity
    with pytest.raises(AttributeError):
        fact.value = 17  # type: ignore[misc]


@pytest.mark.parametrize("field", ["derived_fact_id", "unit", "formula_version"])
def test_empty_semantic_field_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="normalized text"):
        _fact(**{field: ""})


def test_naive_effective_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        _fact(effective_time=datetime(2026, 7, 22, 16, 0))


def test_duplicate_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        _fact(input_evidence=EVIDENCE + EVIDENCE)


def test_evidence_order_does_not_change_identity() -> None:
    other = EvidenceReference(EvidenceKind.OBSERVATION, "analytics:other")
    first = _fact(input_evidence=EVIDENCE + (other,))
    second = _fact(input_evidence=(other,) + EVIDENCE)
    assert first.input_evidence == second.input_evidence
    assert first.identity == second.identity


def test_fact_set_is_ordered_named_and_unique() -> None:
    later = _fact(derived_fact_id="z", value=Decimal("2"))
    earlier = _fact(derived_fact_id="a", value=Decimal("1"))
    facts = DerivedFactSet((later, earlier))
    assert tuple(item.derived_fact_id for item in facts.facts) == ("a", "z")
    assert facts.get("z") is later
    with pytest.raises(ValueError, match="unique"):
        DerivedFactSet((earlier, earlier))
