"""Durable, provider-neutral acquisition attempt records (SPRINT-013 S13-02).

market_data owns the attempt contract and the normalized outcome vocabulary.
Persistence, cycle/pair identity, and query surfaces are owned elsewhere
(asa/integrations, screening, asa/market_data_ops respectively) -- this
module only defines the shape and the pure projection from an already-
computed CapabilityFulfillmentResult.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from domain import MarketCapability
from domain.values import DomainInvariantError, require_tz_aware
from market_data.fulfillment import CapabilityFulfillmentResult, FulfillmentStatus
from market_data.providers import ProviderErrorCode

MAXIMUM_QUERY_LIMIT = 500


class AcquisitionOutcome(str, Enum):
    """SPRINT-013 S13-02's closed, provider-neutral outcome vocabulary."""

    SUCCESS = "success"
    UPSTREAM_RATE_LIMITED = "upstream_rate_limited"
    LOCAL_QUOTA_EXHAUSTED = "local_quota_exhausted"
    EMPTY_PAYLOAD = "empty_payload"
    NO_MATCHING_DATA = "no_matching_data"
    STALE_DATA = "stale_data"
    INCOMPLETE_DATA = "incomplete_data"
    MALFORMED_PAYLOAD = "malformed_payload"
    ENTITLEMENT_UNAVAILABLE = "entitlement_unavailable"
    TRANSPORT_FAILURE = "transport_failure"
    FALLBACK_EXHAUSTED = "fallback_exhausted"


# Closed fold from the wider 17-value ProviderErrorCode vocabulary onto
# S13-02's 11-value normalized outcome list. Several source codes share a
# bucket by design; see project/reports/SPRINT-013-S13-02-notes.md for the
# per-code rationale on the ambiguous folds (auth/entitlement grouped
# together, and the internal-defect-shaped codes folded into
# transport_failure since none of the 11 buckets fit them precisely).
_OUTCOME_BY_ERROR_CODE: dict[ProviderErrorCode, AcquisitionOutcome] = {
    ProviderErrorCode.RATE_LIMITED: AcquisitionOutcome.UPSTREAM_RATE_LIMITED,
    ProviderErrorCode.QUOTA_EXHAUSTED: AcquisitionOutcome.LOCAL_QUOTA_EXHAUSTED,
    ProviderErrorCode.EMPTY_PAYLOAD: AcquisitionOutcome.EMPTY_PAYLOAD,
    ProviderErrorCode.NO_DATA: AcquisitionOutcome.NO_MATCHING_DATA,
    ProviderErrorCode.UNSUPPORTED_CAPABILITY: AcquisitionOutcome.NO_MATCHING_DATA,
    ProviderErrorCode.UNSUPPORTED_SYMBOL: AcquisitionOutcome.NO_MATCHING_DATA,
    ProviderErrorCode.STALE_DATA: AcquisitionOutcome.STALE_DATA,
    ProviderErrorCode.INCOMPLETE_DATA: AcquisitionOutcome.INCOMPLETE_DATA,
    ProviderErrorCode.SCHEMA_MISMATCH: AcquisitionOutcome.MALFORMED_PAYLOAD,
    ProviderErrorCode.ENTITLEMENT_MISSING: AcquisitionOutcome.ENTITLEMENT_UNAVAILABLE,
    ProviderErrorCode.AUTHORIZATION_FAILED: AcquisitionOutcome.ENTITLEMENT_UNAVAILABLE,
    ProviderErrorCode.AUTHENTICATION_FAILED: AcquisitionOutcome.ENTITLEMENT_UNAVAILABLE,
    ProviderErrorCode.TIMEOUT: AcquisitionOutcome.TRANSPORT_FAILURE,
    ProviderErrorCode.PROVIDER_UNAVAILABLE: AcquisitionOutcome.TRANSPORT_FAILURE,
    ProviderErrorCode.TRANSPORT_ERROR: AcquisitionOutcome.TRANSPORT_FAILURE,
    ProviderErrorCode.CONFIGURATION_ERROR: AcquisitionOutcome.TRANSPORT_FAILURE,
    ProviderErrorCode.INVALID_REQUEST: AcquisitionOutcome.TRANSPORT_FAILURE,
    ProviderErrorCode.UNKNOWN_PROVIDER_ERROR: AcquisitionOutcome.TRANSPORT_FAILURE,
}


def normalize_acquisition_outcome(error_code: ProviderErrorCode | None) -> AcquisitionOutcome:
    """Fold a single attempt's provider error code onto the closed S13-02
    outcome vocabulary. ``None`` (no error) always means the attempt
    succeeded. ``FALLBACK_EXHAUSTED`` is never returned here -- it is a
    pair-evaluation-level signal, see ``summary_outcome_for``.
    """
    if error_code is None:
        return AcquisitionOutcome.SUCCESS
    return _OUTCOME_BY_ERROR_CODE[error_code]


def summary_outcome_for(result: CapabilityFulfillmentResult) -> AcquisitionOutcome:
    """The pair-evaluation-level acquisition outcome for one capability
    request: SUCCESS if any candidate was fulfilled (whether the primary
    provider or a fallback), FALLBACK_EXHAUSTED if every candidate failed.

    Individual attempt rows already carry ``fulfillment_status``
    (FULFILLED/DEGRADED/FAILED), which distinguishes a primary-provider
    success from a fallback-provider success; this function is the
    fallback_success_and_failure_are_distinct signal at the request level.
    """
    if result.status is FulfillmentStatus.FAILED:
        return AcquisitionOutcome.FALLBACK_EXHAUSTED
    return AcquisitionOutcome.SUCCESS


@dataclass(frozen=True, slots=True)
class AcquisitionAttemptRecord:
    """One durable, append-only record of a single provider fulfillment
    attempt within one pair evaluation of one screening cycle.

    Carries only safe, generic evidence -- no raw payloads, headers, or
    credentials. ``safe_summary`` is the existing sanitized
    NormalizedProviderError.safe_summary; nothing provider-internal is
    added here. The outcome fold is diagnostically lossless: ``outcome``
    is the aggregate S13-02 bucket (useful for reporting/summaries), and
    ``diagnostic_code`` is always the original, still-safe ProviderErrorCode
    it was folded from -- root-cause analysis never has to guess which of
    several folded codes actually happened.
    """

    screening_cycle_id: str
    pair_evaluation_id: str
    sequence: int
    capability: MarketCapability
    provider_id: str
    priority: int
    fulfillment_status: FulfillmentStatus
    outcome: AcquisitionOutcome
    diagnostic_code: ProviderErrorCode | None
    retryable: bool
    safe_summary: str | None
    recorded_at: datetime

    def __post_init__(self) -> None:
        for name in ("screening_cycle_id", "pair_evaluation_id", "provider_id"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise DomainInvariantError(f"AcquisitionAttemptRecord.{name} must be normalized")
        if type(self.sequence) is not int or self.sequence < 0:
            raise DomainInvariantError("AcquisitionAttemptRecord.sequence must be non-negative")
        if type(self.priority) is not int or self.priority < 1:
            raise DomainInvariantError("AcquisitionAttemptRecord.priority must be positive")
        require_tz_aware(self.recorded_at, "AcquisitionAttemptRecord", "recorded_at")
        if self.outcome is AcquisitionOutcome.SUCCESS:
            if self.safe_summary is not None or self.diagnostic_code is not None:
                raise DomainInvariantError(
                    "AcquisitionAttemptRecord success attempts must not carry "
                    "a safe_summary or diagnostic_code"
                )
        else:
            if self.safe_summary is None or self.diagnostic_code is None:
                raise DomainInvariantError(
                    "AcquisitionAttemptRecord failed attempts require both a "
                    "safe_summary and a diagnostic_code -- the normalized outcome "
                    "fold must stay diagnostically lossless"
                )
            if normalize_acquisition_outcome(self.diagnostic_code) is not self.outcome:
                raise DomainInvariantError(
                    "AcquisitionAttemptRecord.diagnostic_code must fold onto "
                    "the record's own outcome"
                )


def attempt_records_for(
    result: CapabilityFulfillmentResult,
    *,
    screening_cycle_id: str,
    pair_evaluation_id: str,
    recorded_at: datetime,
    sequence_offset: int = 0,
) -> tuple[AcquisitionAttemptRecord, ...]:
    """Project one CapabilityFulfillmentResult's attempt evidence into
    durable, append-only attempt records, deterministically ordered by
    attempt sequence within the pair evaluation (matching
    ``result.attempts`` order, which ``CapabilityFulfillmentService``
    already produces deterministically).
    """
    records: list[AcquisitionAttemptRecord] = []
    for offset, attempt in enumerate(result.attempts):
        error_code = attempt.error.code if attempt.error is not None else None
        outcome = normalize_acquisition_outcome(error_code)
        records.append(
            AcquisitionAttemptRecord(
                screening_cycle_id=screening_cycle_id,
                pair_evaluation_id=pair_evaluation_id,
                sequence=sequence_offset + offset,
                capability=result.request.capability,
                provider_id=attempt.provider_id,
                priority=attempt.priority,
                fulfillment_status=result.status,
                outcome=outcome,
                diagnostic_code=error_code,
                retryable=attempt.error.retryable if attempt.error is not None else False,
                safe_summary=attempt.error.safe_summary if attempt.error is not None else None,
                recorded_at=recorded_at,
            )
        )
    return tuple(records)


@dataclass(frozen=True, slots=True)
class AttemptQuery:
    """Bounded, filtered query for durable attempt records. All filters are
    optional and combine with AND. ``limit`` is always enforced (capped at
    MAXIMUM_QUERY_LIMIT) so no caller -- including operations routes -- can
    request an unbounded result set.
    """

    screening_cycle_id: str | None = None
    pair_evaluation_id: str | None = None
    provider_id: str | None = None
    capability: MarketCapability | None = None
    outcome: AcquisitionOutcome | None = None
    recorded_after: datetime | None = None
    recorded_before: datetime | None = None
    limit: int = 100
    offset: int = 0

    def __post_init__(self) -> None:
        if type(self.limit) is not int or not 1 <= self.limit <= MAXIMUM_QUERY_LIMIT:
            raise ValueError(f"AttemptQuery.limit must be in [1, {MAXIMUM_QUERY_LIMIT}]")
        if type(self.offset) is not int or self.offset < 0:
            raise ValueError("AttemptQuery.offset must be non-negative")
        if self.recorded_after is not None:
            require_tz_aware(self.recorded_after, "AttemptQuery", "recorded_after")
        if self.recorded_before is not None:
            require_tz_aware(self.recorded_before, "AttemptQuery", "recorded_before")
        if (
            self.recorded_after is not None
            and self.recorded_before is not None
            and self.recorded_after > self.recorded_before
        ):
            raise ValueError("AttemptQuery.recorded_after must not be after recorded_before")


@runtime_checkable
class AcquisitionAttemptRepository(Protocol):
    """Append-only durable storage for AcquisitionAttemptRecord. Concrete
    implementations (in-memory, PostgreSQL) must share identical semantics:
    idempotent on (pair_evaluation_id, sequence) -- re-recording the exact
    same attempt is a no-op, never a duplicate row and never an error -- and
    stable-ordered queries (recorded_at, pair_evaluation_id, sequence).
    """

    def record(self, attempts: tuple[AcquisitionAttemptRecord, ...]) -> None: ...

    def query(self, query: AttemptQuery) -> tuple[AcquisitionAttemptRecord, ...]: ...

    def summarize(self, query: AttemptQuery) -> dict[AcquisitionOutcome, int]:
        """Count of matching attempts grouped by outcome. Ignores
        ``query.limit``/``query.offset`` -- a summary counts every matching
        row, not one bounded page of them.
        """
        ...


class InMemoryAcquisitionAttemptRepository:
    """Reference implementation and test double. Production code may also
    use this directly for non-Postgres deployments; asa/integrations owns
    the PostgreSQL-backed implementation with identical semantics.
    """

    def __init__(self) -> None:
        self._rows: list[AcquisitionAttemptRecord] = []
        self._seen: set[tuple[str, int]] = set()

    def record(self, attempts: tuple[AcquisitionAttemptRecord, ...]) -> None:
        for attempt in attempts:
            key = (attempt.pair_evaluation_id, attempt.sequence)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._rows.append(attempt)

    def query(self, query: AttemptQuery) -> tuple[AcquisitionAttemptRecord, ...]:
        matches = [item for item in self._rows if _matches(item, query)]
        matches.sort(key=lambda item: (item.recorded_at, item.pair_evaluation_id, item.sequence))
        return tuple(matches[query.offset : query.offset + query.limit])

    def summarize(self, query: AttemptQuery) -> dict[AcquisitionOutcome, int]:
        counts: dict[AcquisitionOutcome, int] = {}
        for item in self._rows:
            if _matches(item, query):
                counts[item.outcome] = counts.get(item.outcome, 0) + 1
        return counts


def _matches(item: AcquisitionAttemptRecord, query: AttemptQuery) -> bool:
    cycle_ok = (
        query.screening_cycle_id is None or item.screening_cycle_id == query.screening_cycle_id
    )
    pair_ok = (
        query.pair_evaluation_id is None or item.pair_evaluation_id == query.pair_evaluation_id
    )
    return (
        cycle_ok
        and pair_ok
        and (query.provider_id is None or item.provider_id == query.provider_id)
        and (query.capability is None or item.capability is query.capability)
        and (query.outcome is None or item.outcome is query.outcome)
        and (query.recorded_after is None or item.recorded_at >= query.recorded_after)
        and (query.recorded_before is None or item.recorded_at <= query.recorded_before)
    )
