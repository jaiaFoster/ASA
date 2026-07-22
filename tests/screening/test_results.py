from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from domain import EvidenceKind, EvidenceReference
from screening.results import ScreeningOutcomeStatus, ScreeningResult, bounded_failure_detail

AS_OF = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "screening:test-evidence"),)


def _result(**overrides: object) -> ScreeningResult:
    fields: dict[str, object] = {
        "run_id": "run-1",
        "strategy_id": "forward_factor",
        "strategy_version": "1.1.0",
        "subject_identity": "figi:BBG000B9XRY4",
        "as_of": AS_OF,
        "outcome_status": ScreeningOutcomeStatus.PASS,
        "signal_classification": "PASS",
        "strategy_native_score": Decimal("1.25"),
        "evidence": EVIDENCE,
        "input_provenance": EVIDENCE,
        "completeness": None,
        "failure_detail": None,
    }
    fields.update(overrides)
    return ScreeningResult(**fields)  # type: ignore[arg-type]


class TestScreeningResultInvariants:
    def test_valid_pass_result_constructs(self) -> None:
        result = _result()
        assert result.outcome_status is ScreeningOutcomeStatus.PASS

    def test_valid_no_signal_result_constructs_without_score_or_classification(self) -> None:
        result = _result(
            outcome_status=ScreeningOutcomeStatus.NO_SIGNAL,
            signal_classification=None,
            strategy_native_score=None,
        )
        assert result.signal_classification is None
        assert result.strategy_native_score is None

    @pytest.mark.parametrize(
        "status",
        [
            ScreeningOutcomeStatus.MISSING_DATA,
            ScreeningOutcomeStatus.MALFORMED_OUTPUT,
            ScreeningOutcomeStatus.STRATEGY_EXCEPTION,
        ],
    )
    def test_failure_status_requires_failure_detail(self, status: ScreeningOutcomeStatus) -> None:
        with pytest.raises(ValueError, match="requires failure_detail"):
            _result(
                outcome_status=status,
                signal_classification=None,
                strategy_native_score=None,
                evidence=(),
                input_provenance=(),
                failure_detail=None,
            )

    def test_success_status_forbids_failure_detail(self) -> None:
        with pytest.raises(ValueError, match="must not carry failure_detail"):
            _result(failure_detail="should not be set")

    def test_failure_status_forbids_signal_classification(self) -> None:
        with pytest.raises(ValueError, match="must not carry signal_classification"):
            _result(
                outcome_status=ScreeningOutcomeStatus.MISSING_DATA,
                signal_classification="PASS",
                strategy_native_score=None,
                evidence=(),
                input_provenance=(),
                failure_detail="missing option chain",
            )

    def test_failure_status_forbids_synthesized_score(self) -> None:
        """No score may be synthesized for a non-success outcome."""
        with pytest.raises(ValueError, match="must not carry strategy_native_score"):
            _result(
                outcome_status=ScreeningOutcomeStatus.MISSING_DATA,
                signal_classification=None,
                strategy_native_score=Decimal("0"),
                evidence=(),
                input_provenance=(),
                failure_detail="missing option chain",
            )

    def test_pass_requires_signal_classification(self) -> None:
        with pytest.raises(ValueError, match="requires signal_classification for outcome_status PASS"):
            _result(signal_classification=None)

    def test_naive_as_of_rejected(self) -> None:
        with pytest.raises(ValueError):
            _result(as_of=datetime(2026, 7, 22, 16, 0))

    @pytest.mark.parametrize(
        "field", ["run_id", "strategy_id", "strategy_version", "subject_identity"]
    )
    def test_empty_identity_field_rejected(self, field: str) -> None:
        with pytest.raises(ValueError, match="normalized text"):
            _result(**{field: ""})


class TestBoundedFailureDetail:
    def test_short_text_is_unchanged(self) -> None:
        assert bounded_failure_detail("short reason") == "short reason"

    def test_long_text_is_truncated(self) -> None:
        text = "x" * 1000
        bounded = bounded_failure_detail(text)
        assert len(bounded) == 500
        assert bounded.endswith("...")

    def test_surrounding_whitespace_is_stripped(self) -> None:
        assert bounded_failure_detail("  padded  ") == "padded"
