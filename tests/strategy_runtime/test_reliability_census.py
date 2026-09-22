from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain import MarketCapability
from market_data.attempts import AcquisitionAttemptRecord, AcquisitionOutcome
from market_data.fulfillment import FulfillmentStatus
from market_data.providers import ProviderErrorCode
from strategy_runtime.reliability_census import (
    ExpectedCapabilityDemand,
    LatestResultEvidence,
    MissingnessClass,
    MissingnessOwner,
    SubjectAttemptEvidence,
    build_missingness_census,
)

NOW = datetime(2026, 9, 21, tzinfo=UTC)


def _attempt(
    capability: MarketCapability,
    code: ProviderErrorCode | None = None,
    *,
    sequence: int = 0,
) -> AcquisitionAttemptRecord:
    outcome = {
        None: AcquisitionOutcome.SUCCESS,
        ProviderErrorCode.STALE_DATA: AcquisitionOutcome.STALE_DATA,
        ProviderErrorCode.RATE_LIMITED: AcquisitionOutcome.UPSTREAM_RATE_LIMITED,
        ProviderErrorCode.ENTITLEMENT_MISSING: AcquisitionOutcome.ENTITLEMENT_UNAVAILABLE,
        ProviderErrorCode.NO_DATA: AcquisitionOutcome.NO_MATCHING_DATA,
        ProviderErrorCode.INVALID_REQUEST: AcquisitionOutcome.TRANSPORT_FAILURE,
    }[code]
    return AcquisitionAttemptRecord(
        screening_cycle_id="cycle-1",
        pair_evaluation_id="cycle-1:SPY",
        sequence=sequence,
        capability=capability,
        provider_id="fixture",
        priority=1,
        fulfillment_status=(
            FulfillmentStatus.FULFILLED if code is None else FulfillmentStatus.FAILED
        ),
        outcome=outcome,
        diagnostic_code=code,
        retryable=code is ProviderErrorCode.RATE_LIMITED,
        safe_summary=None if code is None else "sanitized",
        recorded_at=NOW,
    )


@pytest.mark.parametrize(
    ("code", "expected_class", "expected_owner"),
    [
        (None, MissingnessClass.CURRENT_USABLE, MissingnessOwner.NOT_APPLICABLE),
        (ProviderErrorCode.STALE_DATA, MissingnessClass.STALE, MissingnessOwner.UNRESOLVED),
        (
            ProviderErrorCode.RATE_LIMITED,
            MissingnessClass.PROVIDER_FAILURE,
            MissingnessOwner.PROVIDER_EXTERNAL,
        ),
        (
            ProviderErrorCode.ENTITLEMENT_MISSING,
            MissingnessClass.ENTITLEMENT_OR_COVERAGE,
            MissingnessOwner.PROVIDER_EXTERNAL,
        ),
        (
            ProviderErrorCode.INVALID_REQUEST,
            MissingnessClass.IDENTITY_MAPPING_OR_CANONICALIZATION,
            MissingnessOwner.ASA,
        ),
    ],
)
def test_attempt_failures_keep_owning_boundary(
    code: ProviderErrorCode | None,
    expected_class: MissingnessClass,
    expected_owner: MissingnessOwner,
) -> None:
    demand = ExpectedCapabilityDemand("B001", "SPY", MarketCapability.REAL_TIME_QUOTE_V1)
    result = build_missingness_census(
        (demand,),
        (SubjectAttemptEvidence("SPY", _attempt(MarketCapability.REAL_TIME_QUOTE_V1, code)),),
        diagnostics_complete=True,
    )
    assert result.rows[0].classification is expected_class
    assert result.rows[0].owner is expected_owner


def test_shared_subject_attempt_is_projected_only_to_exact_declared_consumers() -> None:
    demands = (
        ExpectedCapabilityDemand("B001", "SPY", MarketCapability.REAL_TIME_QUOTE_V1),
        ExpectedCapabilityDemand("B002", "SPY", MarketCapability.REAL_TIME_QUOTE_V1),
        ExpectedCapabilityDemand("B002", "SPY", MarketCapability.HISTORICAL_BARS_V1),
    )
    result = build_missingness_census(
        demands,
        (SubjectAttemptEvidence("SPY", _attempt(MarketCapability.REAL_TIME_QUOTE_V1)),),
        diagnostics_complete=True,
    )
    assert [row.classification for row in result.rows] == [
        MissingnessClass.CURRENT_USABLE,
        MissingnessClass.ACQUISITION_NOT_EXECUTED,
        MissingnessClass.CURRENT_USABLE,
    ]


def test_missing_attempt_never_claims_not_executed_when_diagnostics_degraded() -> None:
    demand = ExpectedCapabilityDemand("B001", "SPY", MarketCapability.REAL_TIME_QUOTE_V1)
    result = build_missingness_census((), (), diagnostics_complete=False)
    assert result.rows == ()
    result = build_missingness_census((demand,), (), diagnostics_complete=False)
    assert result.rows[0].classification is MissingnessClass.DIAGNOSTIC_GAP
    assert result.rows[0].owner is MissingnessOwner.ASA


def test_authoritative_no_data_differs_from_unconfirmed_provider_absence() -> None:
    demand = ExpectedCapabilityDemand(
        "earnings_calendar", "SPY", MarketCapability.EARNINGS_CALENDAR_V1
    )
    attempt = _attempt(MarketCapability.EARNINGS_CALENDAR_V1, ProviderErrorCode.NO_DATA)
    unconfirmed = build_missingness_census(
        (demand,), (SubjectAttemptEvidence("SPY", attempt),), diagnostics_complete=True
    )
    confirmed = build_missingness_census(
        (demand,),
        (SubjectAttemptEvidence("SPY", attempt, authoritative_absence_confirmed=True),),
        diagnostics_complete=True,
    )
    assert unconfirmed.rows[0].owner is MissingnessOwner.PROVIDER_EXTERNAL
    assert confirmed.rows[0].owner is MissingnessOwner.LEGITIMATELY_UNAVAILABLE


def test_latest_typed_result_reason_refines_successful_acquisition() -> None:
    demand = ExpectedCapabilityDemand(
        "earnings_calendar", "SPY", MarketCapability.EARNINGS_CALENDAR_V1
    )
    result = build_missingness_census(
        (demand,),
        (SubjectAttemptEvidence("SPY", _attempt(MarketCapability.EARNINGS_CALENDAR_V1)),),
        (LatestResultEvidence("earnings_calendar", "SPY", "missing_earnings_date"),),
        diagnostics_complete=True,
    )
    assert result.rows[0].classification is MissingnessClass.GENUINELY_UNKNOWN_OR_UNANNOUNCED
    assert result.rows[0].owner is MissingnessOwner.UNRESOLVED


@pytest.mark.parametrize(
    ("reason", "expected_class", "expected_owner"),
    [
        (
            "no_valid_expiration_pair (target_gap=30;tolerance=5)",
            MissingnessClass.TEMPORALLY_UNAVAILABLE,
            MissingnessOwner.LEGITIMATELY_UNAVAILABLE,
        ),
        (
            "missing_implied_volatility",
            MissingnessClass.ENTITLEMENT_OR_COVERAGE,
            MissingnessOwner.PROVIDER_EXTERNAL,
        ),
        (
            "unusable_phase_two_evidence (unusable_roles=front_chain)",
            MissingnessClass.ENTITLEMENT_OR_COVERAGE,
            MissingnessOwner.PROVIDER_EXTERNAL,
        ),
    ],
)
def test_persisted_result_reason_keeps_stable_identifier_classification(
    reason: str,
    expected_class: MissingnessClass,
    expected_owner: MissingnessOwner,
) -> None:
    demand = ExpectedCapabilityDemand(
        "earnings_calendar", "SPY", MarketCapability.EARNINGS_CALENDAR_V1
    )
    result = build_missingness_census(
        (demand,),
        (SubjectAttemptEvidence("SPY", _attempt(MarketCapability.EARNINGS_CALENDAR_V1)),),
        (LatestResultEvidence("earnings_calendar", "SPY", reason),),
        diagnostics_complete=True,
    )
    assert result.rows[0].classification is expected_class
    assert result.rows[0].owner is expected_owner


def test_counts_reconcile_exactly_and_are_deterministic() -> None:
    demands = (
        ExpectedCapabilityDemand("B002", "SPY", MarketCapability.HISTORICAL_BARS_V1),
        ExpectedCapabilityDemand("B001", "SPY", MarketCapability.REAL_TIME_QUOTE_V1),
    )
    result = build_missingness_census(
        demands,
        (SubjectAttemptEvidence("SPY", _attempt(MarketCapability.REAL_TIME_QUOTE_V1)),),
        diagnostics_complete=True,
    )
    assert sum(count for _, count in result.counts) == len(result.rows) == 2
    assert result.rows == tuple(
        sorted(result.rows, key=lambda row: (row.strategy_id, row.symbol, row.capability.value))
    )
