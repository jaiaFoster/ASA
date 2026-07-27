from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain import FreshnessMetadata, FreshnessStatus
from market_data.temporal import (
    FreshnessRequirement,
    TemporalWarningCode,
    UsabilityStatus,
    evaluate_temporal_usability,
)

NOW = datetime(2026, 7, 25, 16, tzinfo=UTC)


def _freshness(status: FreshnessStatus, age: int) -> FreshnessMetadata:
    return FreshnessMetadata(
        NOW,
        datetime.fromtimestamp(NOW.timestamp() - age, tz=UTC),
        3600,
        age,
        status,
    )


def test_default_policy_accepts_prior_session_with_warning() -> None:
    decision = evaluate_temporal_usability(
        _freshness(FreshnessStatus.PRIOR_SESSION, 72_000),
        market_is_open=False,
    )
    assert decision.status is UsabilityStatus.USABLE_WITH_WARNING
    assert decision.warning_codes == (TemporalWarningCode.PRIOR_SESSION_DATA,)


def test_contract_can_reject_prior_session_without_named_branch() -> None:
    decision = evaluate_temporal_usability(
        _freshness(FreshnessStatus.PRIOR_SESSION, 72_000),
        FreshnessRequirement(allow_prior_session=False),
        market_is_open=False,
    )
    assert decision.status is UsabilityStatus.REJECTED


def test_contract_can_require_open_session() -> None:
    decision = evaluate_temporal_usability(
        _freshness(FreshnessStatus.FRESH, 60),
        FreshnessRequirement(require_open_session=True),
        market_is_open=False,
    )
    assert decision.status is UsabilityStatus.REJECTED


def test_invalid_policy_limits_fail_fast() -> None:
    with pytest.raises(ValueError):
        FreshnessRequirement(maximum_age_seconds=-1)
