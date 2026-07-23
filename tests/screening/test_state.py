"""API-001: ScreeningStateRecord construction tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from screening.results import ScreeningOutcomeStatus, ScreeningResult
from screening.state import ScreeningStateRecord

NOW = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)


def _result(
    outcome_status: ScreeningOutcomeStatus = ScreeningOutcomeStatus.PASS,
    signal_classification: str | None = "PASS",
    strategy_native_score: Decimal | None = Decimal("75"),
    failure_detail: str | None = None,
    subject_identity: str = "symbol:AAPL",
) -> ScreeningResult:
    return ScreeningResult(
        "run-1",
        "forward_factor",
        "1.1.0",
        subject_identity,
        NOW,
        outcome_status,
        signal_classification,
        strategy_native_score,
        (),
        (),
        None,
        failure_detail,
    )


class TestFromResult:
    def test_uses_the_caller_supplied_symbol_not_subject_identity(self) -> None:
        record = ScreeningStateRecord.from_result(_result(), symbol="AAPL")
        assert record.symbol == "AAPL"

    def test_maps_core_fields(self) -> None:
        record = ScreeningStateRecord.from_result(_result(), symbol="AAPL")
        assert record.signal_id == "forward_factor"
        assert record.signal_version == "1.1.0"
        assert record.outcome == "pass"
        assert record.explanation == "PASS"
        assert record.metrics == {"strategy_native_score": "75"}
        assert record.updated_at == NOW

    def test_defaults_dependency_timestamps_to_as_of(self) -> None:
        record = ScreeningStateRecord.from_result(_result(), symbol="AAPL")
        assert record.dependency_timestamps == {"as_of": NOW}

    def test_explicit_dependency_timestamps_override_the_default(self) -> None:
        custom = {"quote": NOW}
        record = ScreeningStateRecord.from_result(
            _result(), symbol="AAPL", dependency_timestamps=custom
        )
        assert record.dependency_timestamps == custom

    def test_failure_result_uses_failure_detail_as_explanation(self) -> None:
        result = _result(
            outcome_status=ScreeningOutcomeStatus.MISSING_DATA,
            signal_classification=None,
            strategy_native_score=None,
            failure_detail="could not acquire live quote",
        )
        record = ScreeningStateRecord.from_result(result, symbol="AAPL")
        assert record.explanation == "could not acquire live quote"
        assert record.metrics == {}

    def test_works_even_when_subject_identity_is_unknown(self) -> None:
        # runner.py's own convention: any StrategyAdapterError-raised
        # failure (MISSING_DATA before a subject was ever resolved) sets
        # subject_identity to the literal string "unknown" -- the caller-
        # supplied symbol must still be used, not derived from the result.
        result = _result(
            outcome_status=ScreeningOutcomeStatus.MISSING_DATA,
            signal_classification=None,
            strategy_native_score=None,
            failure_detail="could not acquire live quote",
            subject_identity="unknown",
        )
        record = ScreeningStateRecord.from_result(result, symbol="AAPL")
        assert record.symbol == "AAPL"
