from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain.values import DomainInvariantError
from market_data import FulfillmentStatus, ProviderErrorCode
from market_data.attempts import (
    MAXIMUM_QUERY_LIMIT,
    AcquisitionAttemptRecord,
    AcquisitionOutcome,
    AttemptQuery,
    InMemoryAcquisitionAttemptRepository,
    attempt_records_for,
    normalize_acquisition_outcome,
    summary_outcome_for,
)
from tests.market_data.test_fulfillment import (
    CAPABILITY,
    FixtureScenario,
    provider,
    request,
    service,
)

RECORDED_AT = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)


def test_normalize_acquisition_outcome_success_is_none_error() -> None:
    assert normalize_acquisition_outcome(None) is AcquisitionOutcome.SUCCESS


@pytest.mark.parametrize(
    "code,expected",
    [
        (ProviderErrorCode.RATE_LIMITED, AcquisitionOutcome.UPSTREAM_RATE_LIMITED),
        (ProviderErrorCode.QUOTA_EXHAUSTED, AcquisitionOutcome.LOCAL_QUOTA_EXHAUSTED),
        (ProviderErrorCode.EMPTY_PAYLOAD, AcquisitionOutcome.EMPTY_PAYLOAD),
        (ProviderErrorCode.NO_DATA, AcquisitionOutcome.NO_MATCHING_DATA),
        (ProviderErrorCode.UNSUPPORTED_CAPABILITY, AcquisitionOutcome.NO_MATCHING_DATA),
        (ProviderErrorCode.UNSUPPORTED_SYMBOL, AcquisitionOutcome.NO_MATCHING_DATA),
        (ProviderErrorCode.STALE_DATA, AcquisitionOutcome.STALE_DATA),
        (ProviderErrorCode.INCOMPLETE_DATA, AcquisitionOutcome.INCOMPLETE_DATA),
        (ProviderErrorCode.SCHEMA_MISMATCH, AcquisitionOutcome.MALFORMED_PAYLOAD),
        (ProviderErrorCode.ENTITLEMENT_MISSING, AcquisitionOutcome.ENTITLEMENT_UNAVAILABLE),
        (ProviderErrorCode.AUTHORIZATION_FAILED, AcquisitionOutcome.ENTITLEMENT_UNAVAILABLE),
        (ProviderErrorCode.AUTHENTICATION_FAILED, AcquisitionOutcome.ENTITLEMENT_UNAVAILABLE),
        (ProviderErrorCode.TIMEOUT, AcquisitionOutcome.TRANSPORT_FAILURE),
        (ProviderErrorCode.PROVIDER_UNAVAILABLE, AcquisitionOutcome.TRANSPORT_FAILURE),
        (ProviderErrorCode.TRANSPORT_ERROR, AcquisitionOutcome.TRANSPORT_FAILURE),
        (ProviderErrorCode.CONFIGURATION_ERROR, AcquisitionOutcome.TRANSPORT_FAILURE),
        (ProviderErrorCode.INVALID_REQUEST, AcquisitionOutcome.TRANSPORT_FAILURE),
        (ProviderErrorCode.UNKNOWN_PROVIDER_ERROR, AcquisitionOutcome.TRANSPORT_FAILURE),
    ],
)
def test_normalize_acquisition_outcome_covers_every_provider_error_code(code, expected) -> None:
    assert normalize_acquisition_outcome(code) is expected


def test_every_provider_error_code_is_mapped() -> None:
    for code in ProviderErrorCode:
        # Must not raise KeyError -- every code has a bucket.
        normalize_acquisition_outcome(code)


def test_attempt_record_requires_summary_and_diagnostic_code_iff_not_success() -> None:
    with pytest.raises(DomainInvariantError):
        AcquisitionAttemptRecord(
            "cycle_1", "cycle_1:s:AAPL", 0, CAPABILITY, "primary", 1,
            FulfillmentStatus.FULFILLED, AcquisitionOutcome.SUCCESS, None, False,
            "unexpected summary", RECORDED_AT,
        )
    with pytest.raises(DomainInvariantError):
        AcquisitionAttemptRecord(
            "cycle_1", "cycle_1:s:AAPL", 0, CAPABILITY, "primary", 1,
            FulfillmentStatus.FULFILLED, AcquisitionOutcome.SUCCESS,
            ProviderErrorCode.TIMEOUT, False, None, RECORDED_AT,
        )
    with pytest.raises(DomainInvariantError):
        AcquisitionAttemptRecord(
            "cycle_1", "cycle_1:s:AAPL", 0, CAPABILITY, "primary", 1,
            FulfillmentStatus.FAILED, AcquisitionOutcome.TRANSPORT_FAILURE, None, True,
            "a summary but no diagnostic code", RECORDED_AT,
        )
    with pytest.raises(DomainInvariantError):
        AcquisitionAttemptRecord(
            "cycle_1", "cycle_1:s:AAPL", 0, CAPABILITY, "primary", 1,
            FulfillmentStatus.FAILED, AcquisitionOutcome.TRANSPORT_FAILURE,
            ProviderErrorCode.TIMEOUT, True, None, RECORDED_AT,
        )


def test_attempt_record_rejects_diagnostic_code_that_does_not_fold_onto_outcome() -> None:
    with pytest.raises(DomainInvariantError):
        AcquisitionAttemptRecord(
            "cycle_1", "cycle_1:s:AAPL", 0, CAPABILITY, "primary", 1,
            FulfillmentStatus.FAILED, AcquisitionOutcome.TRANSPORT_FAILURE,
            ProviderErrorCode.NO_DATA,  # folds to NO_MATCHING_DATA, not TRANSPORT_FAILURE
            True, "mismatched diagnostic code", RECORDED_AT,
        )


def test_attempt_records_for_success_result_is_single_record() -> None:
    fulfillment, _ = service(provider("primary"))
    result = fulfillment.fulfill(request())
    records = attempt_records_for(
        result,
        screening_cycle_id="cycle_1",
        pair_evaluation_id="cycle_1:forward_factor:AAPL",
        recorded_at=RECORDED_AT,
    )
    assert len(records) == 1
    assert records[0].outcome is AcquisitionOutcome.SUCCESS
    assert records[0].fulfillment_status is FulfillmentStatus.FULFILLED
    assert records[0].sequence == 0
    assert records[0].safe_summary is None
    assert records[0].diagnostic_code is None
    assert summary_outcome_for(result) is AcquisitionOutcome.SUCCESS


def test_attempt_records_for_degraded_result_preserves_order_and_fallback_success() -> None:
    primary = provider(
        "primary", FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.TIMEOUT),))
    )
    fulfillment, _ = service(primary, provider("secondary"))
    result = fulfillment.fulfill(request())
    records = attempt_records_for(
        result,
        screening_cycle_id="cycle_1",
        pair_evaluation_id="cycle_1:forward_factor:AAPL",
        recorded_at=RECORDED_AT,
    )
    assert len(records) == 2
    assert [item.sequence for item in records] == [0, 1]
    assert records[0].provider_id == "primary"
    assert records[0].outcome is AcquisitionOutcome.TRANSPORT_FAILURE
    assert records[0].diagnostic_code is ProviderErrorCode.TIMEOUT
    assert records[0].fulfillment_status is FulfillmentStatus.DEGRADED
    assert records[0].safe_summary is not None
    assert records[1].provider_id == "secondary"
    assert records[1].outcome is AcquisitionOutcome.SUCCESS
    assert records[1].diagnostic_code is None
    assert records[1].fulfillment_status is FulfillmentStatus.DEGRADED
    # Fallback succeeded (DEGRADED), distinct from fallback exhausted (FAILED).
    assert summary_outcome_for(result) is AcquisitionOutcome.SUCCESS


def test_attempt_records_for_failed_result_is_fallback_exhausted() -> None:
    failed = FixtureScenario(failures=((CAPABILITY, ProviderErrorCode.NO_DATA),))
    fulfillment, _ = service(provider("primary", failed), provider("secondary", failed))
    result = fulfillment.fulfill(request(), required=False)
    records = attempt_records_for(
        result,
        screening_cycle_id="cycle_1",
        pair_evaluation_id="cycle_1:forward_factor:AAPL",
        recorded_at=RECORDED_AT,
    )
    assert len(records) == 2
    assert all(item.fulfillment_status is FulfillmentStatus.FAILED for item in records)
    assert all(item.outcome is AcquisitionOutcome.NO_MATCHING_DATA for item in records)
    assert all(item.diagnostic_code is ProviderErrorCode.NO_DATA for item in records)
    assert summary_outcome_for(result) is AcquisitionOutcome.FALLBACK_EXHAUSTED


def test_attempt_records_for_sequence_offset_continues_across_capabilities() -> None:
    fulfillment, _ = service(provider("primary"))
    result = fulfillment.fulfill(request())
    records = attempt_records_for(
        result,
        screening_cycle_id="cycle_1",
        pair_evaluation_id="cycle_1:forward_factor:AAPL",
        recorded_at=RECORDED_AT,
        sequence_offset=3,
    )
    assert records[0].sequence == 3


# -- InMemoryAcquisitionAttemptRepository (contract also proven for
# PostgresAcquisitionAttemptRepository in
# tests/asa/test_screening_acquisition_attempts_postgres.py) --------------


def _record(
    *,
    pair: str = "cycle_1:forward_factor:AAPL",
    sequence: int = 0,
    provider_id: str = "primary",
    outcome: AcquisitionOutcome = AcquisitionOutcome.SUCCESS,
    diagnostic_code: ProviderErrorCode | None = None,
    recorded_at: datetime = RECORDED_AT,
    capability=CAPABILITY,
) -> AcquisitionAttemptRecord:
    failed = outcome is not AcquisitionOutcome.SUCCESS
    return AcquisitionAttemptRecord(
        "cycle_1",
        pair,
        sequence,
        capability,
        provider_id,
        1,
        FulfillmentStatus.FULFILLED if not failed else FulfillmentStatus.FAILED,
        outcome,
        diagnostic_code if failed else None,
        failed,
        "a safe summary" if failed else None,
        recorded_at,
    )


def test_repository_record_and_query_round_trip() -> None:
    repo = InMemoryAcquisitionAttemptRepository()
    repo.record((_record(),))
    results = repo.query(AttemptQuery(screening_cycle_id="cycle_1"))
    assert len(results) == 1
    assert results[0].pair_evaluation_id == "cycle_1:forward_factor:AAPL"


def test_repository_record_is_idempotent_on_pair_and_sequence() -> None:
    """Re-recording the exact same (pair_evaluation_id, sequence) is a
    no-op -- not a duplicate row, not an error."""
    repo = InMemoryAcquisitionAttemptRepository()
    repo.record((_record(),))
    repo.record((_record(),))
    results = repo.query(AttemptQuery(screening_cycle_id="cycle_1"))
    assert len(results) == 1


def test_repository_does_not_collapse_a_genuinely_new_attempt() -> None:
    """A legitimate retry -- a new attempt with the next sequence number --
    must still get its own row, never collapsed by idempotency."""
    repo = InMemoryAcquisitionAttemptRepository()
    repo.record((_record(sequence=0),))
    repo.record((_record(sequence=1, provider_id="secondary"),))
    results = repo.query(AttemptQuery(screening_cycle_id="cycle_1"))
    assert len(results) == 2


def test_repository_query_filters_by_provider_capability_outcome_and_time() -> None:
    repo = InMemoryAcquisitionAttemptRepository()
    repo.record(
        (
            _record(sequence=0, provider_id="primary", outcome=AcquisitionOutcome.SUCCESS),
            _record(
                sequence=1,
                provider_id="secondary",
                outcome=AcquisitionOutcome.TRANSPORT_FAILURE,
                diagnostic_code=ProviderErrorCode.TRANSPORT_ERROR,
                recorded_at=RECORDED_AT + timedelta(minutes=5),
            ),
        )
    )
    assert len(repo.query(AttemptQuery(provider_id="secondary"))) == 1
    assert len(repo.query(AttemptQuery(capability=CAPABILITY))) == 2
    assert len(repo.query(AttemptQuery(outcome=AcquisitionOutcome.TRANSPORT_FAILURE))) == 1
    assert len(repo.query(AttemptQuery(recorded_after=RECORDED_AT + timedelta(minutes=1)))) == 1
    assert len(repo.query(AttemptQuery(recorded_before=RECORDED_AT))) == 1


def test_repository_query_pagination_and_stable_ordering() -> None:
    repo = InMemoryAcquisitionAttemptRepository()
    repo.record(
        tuple(
            _record(
                pair=f"cycle_1:forward_factor:SYM{i}",
                sequence=0,
                recorded_at=RECORDED_AT + timedelta(seconds=i),
            )
            for i in range(5)
        )
    )
    first_page = repo.query(AttemptQuery(limit=2, offset=0))
    second_page = repo.query(AttemptQuery(limit=2, offset=2))
    assert [item.pair_evaluation_id for item in first_page] == [
        "cycle_1:forward_factor:SYM0",
        "cycle_1:forward_factor:SYM1",
    ]
    assert [item.pair_evaluation_id for item in second_page] == [
        "cycle_1:forward_factor:SYM2",
        "cycle_1:forward_factor:SYM3",
    ]


def test_attempt_query_rejects_limit_above_maximum() -> None:
    with pytest.raises(ValueError):
        AttemptQuery(limit=MAXIMUM_QUERY_LIMIT + 1)


def test_attempt_query_rejects_inverted_time_range() -> None:
    with pytest.raises(ValueError):
        AttemptQuery(recorded_after=RECORDED_AT, recorded_before=RECORDED_AT - timedelta(hours=1))


def test_repository_summarize_groups_by_outcome_ignoring_pagination() -> None:
    repo = InMemoryAcquisitionAttemptRepository()
    repo.record(
        (
            _record(sequence=0, outcome=AcquisitionOutcome.SUCCESS),
            _record(
                pair="cycle_1:forward_factor:MSFT",
                sequence=0,
                outcome=AcquisitionOutcome.TRANSPORT_FAILURE,
                diagnostic_code=ProviderErrorCode.TRANSPORT_ERROR,
            ),
            _record(
                pair="cycle_1:forward_factor:GOOG",
                sequence=0,
                outcome=AcquisitionOutcome.TRANSPORT_FAILURE,
                diagnostic_code=ProviderErrorCode.TIMEOUT,
            ),
        )
    )
    counts = repo.summarize(AttemptQuery(screening_cycle_id="cycle_1", limit=1))
    assert counts == {
        AcquisitionOutcome.SUCCESS: 1,
        AcquisitionOutcome.TRANSPORT_FAILURE: 2,
    }
