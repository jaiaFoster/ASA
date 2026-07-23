"""SPRINT-009/EPIC-6: proves the universal envelope fits all three
EPIC-7 migration targets without a field that only makes sense for one
of them -- EPIC-6's own acceptance criterion. forward_factor and
skew_momentum_vertical share an identical shape (no lifecycle);
earnings_calendar is deliberately the one that populates the
lifecycle-specific fields, proving the same envelope handles both cases
without a strategy-specific branch anywhere in this module -- these are
just three different sets of field values on one dataclass.
"""

from __future__ import annotations

from datetime import UTC, datetime

from strategy_runtime.result import (
    EvaluationState,
    RowType,
    UniversalScreeningResult,
    compute_observation_id,
)

_RUN_ID = "example-run-id"
_OBSERVED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _no_lifecycle_result(strategy_id: str, strategy_version: str) -> UniversalScreeningResult:
    return UniversalScreeningResult(
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        symbol="AAPL",
        observation_id=compute_observation_id(_RUN_ID, strategy_id, "AAPL"),
        opportunity_id=None,
        row_type=RowType.RESULT,
        verdict="pass",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage=None,
        recommendation_state=None,
        data_quality="fresh",
        metrics={"strategy_native_score": "0.42"},
        economics={"debit": "1.25"},
        blockers=(),
        warnings=(),
        provenance=("tradier:option_chain_v1",),
        observed_at=_OBSERVED_AT,
    )


def test_forward_factor_fits_the_universal_envelope() -> None:
    result = _no_lifecycle_result("forward_factor", "1.1.0")
    assert result.opportunity_id is None
    assert result.lifecycle_stage is None
    assert result.metrics["strategy_native_score"] == "0.42"


def test_skew_momentum_vertical_fits_the_universal_envelope() -> None:
    result = _no_lifecycle_result("skew_momentum", "1.0.0")
    assert result.opportunity_id is None
    assert result.lifecycle_stage is None


def test_earnings_calendar_fits_the_universal_envelope_including_lifecycle_fields() -> None:
    strategy_id = "earnings_calendar"
    observation_id = compute_observation_id(_RUN_ID, strategy_id, "AAPL")
    result = UniversalScreeningResult(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        symbol="AAPL",
        observation_id=observation_id,
        opportunity_id=f"opportunity:{strategy_id}:AAPL:2026-02-01",
        row_type=RowType.RESULT,
        verdict="true_earnings_iv_crush_calendar",
        evaluation_state=EvaluationState.PASS,
        lifecycle_stage="watching",
        recommendation_state=None,
        data_quality="fresh",
        metrics={"strategy_native_score": "0.71"},
        economics={"debit": "0.85"},
        blockers=(),
        warnings=("earnings_timestamp_unconfirmed",),
        provenance=("tradier:option_chain_v1", "finnhub:earnings_calendar_v1"),
        observed_at=_OBSERVED_AT,
    )
    assert result.opportunity_id is not None
    assert result.lifecycle_stage == "watching"
    assert result.verdict == "true_earnings_iv_crush_calendar"


def test_all_three_share_the_same_envelope_type_not_three_different_shapes() -> None:
    forward_factor = _no_lifecycle_result("forward_factor", "1.1.0")
    skew_momentum = _no_lifecycle_result("skew_momentum", "1.0.0")
    assert type(forward_factor) is type(skew_momentum) is UniversalScreeningResult
