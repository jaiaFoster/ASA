"""Deterministic, provider-neutral missingness ownership census.

The census combines declared consumer demand, subject-scoped acquisition
attempts, and latest typed result reasons.  It deliberately does not interpret
``pair_evaluation_id`` as a strategy identity: shared subject preparation owns
that identifier in production.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from domain import MarketCapability
from market_data.attempts import AcquisitionAttemptRecord
from market_data.providers import ProviderErrorCode


class MissingnessClass(StrEnum):
    CURRENT_USABLE = "current_usable"
    STALE = "stale"
    ACQUISITION_NOT_EXECUTED = "acquisition_not_executed"
    PROVIDER_FAILURE = "provider_failure"
    ENTITLEMENT_OR_COVERAGE = "entitlement_or_coverage"
    IDENTITY_MAPPING_OR_CANONICALIZATION = "identity_mapping_or_canonicalization"
    DERIVATION_OR_INSUFFICIENT_HISTORY = "derivation_or_insufficient_history"
    TEMPORALLY_UNAVAILABLE = "temporally_unavailable"
    GENUINELY_UNKNOWN_OR_UNANNOUNCED = "genuinely_unknown_or_unannounced"
    DIAGNOSTIC_GAP = "diagnostic_gap"


class MissingnessOwner(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    ASA = "asa_owned"
    PROVIDER_EXTERNAL = "provider_external"
    LEGITIMATELY_UNAVAILABLE = "legitimately_unavailable"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ExpectedCapabilityDemand:
    strategy_id: str
    symbol: str
    capability: MarketCapability


@dataclass(frozen=True, slots=True)
class SubjectAttemptEvidence:
    symbol: str
    attempt: AcquisitionAttemptRecord
    authoritative_absence_confirmed: bool = False


@dataclass(frozen=True, slots=True)
class LatestResultEvidence:
    strategy_id: str
    symbol: str
    reason: str


@dataclass(frozen=True, slots=True)
class CensusRow:
    strategy_id: str
    symbol: str
    capability: MarketCapability
    provider_id: str | None
    classification: MissingnessClass
    owner: MissingnessOwner
    reason: str


@dataclass(frozen=True, slots=True)
class MissingnessCensus:
    rows: tuple[CensusRow, ...]
    counts: tuple[tuple[str, int], ...]


def build_missingness_census(
    demands: tuple[ExpectedCapabilityDemand, ...],
    attempts: tuple[SubjectAttemptEvidence, ...],
    latest_results: tuple[LatestResultEvidence, ...] = (),
    *,
    diagnostics_complete: bool,
) -> MissingnessCensus:
    """Classify every expected demand without inventing pair attribution.

    One subject/capability attempt is intentionally projected to every declared
    consumer of that exact subject/capability.  Missing attempts are called
    ``acquisition_not_executed`` only when the caller proves diagnostics were
    complete; otherwise they remain an ASA-owned diagnostic gap.
    """

    attempt_by_key: dict[tuple[str, MarketCapability], SubjectAttemptEvidence] = {}
    for attempt_evidence in attempts:
        key = (attempt_evidence.symbol, attempt_evidence.attempt.capability)
        prior = attempt_by_key.get(key)
        if prior is None or attempt_evidence.attempt.sequence > prior.attempt.sequence:
            attempt_by_key[key] = attempt_evidence

    reason_by_pair = {
        (item.strategy_id, item.symbol): item.reason for item in latest_results
    }
    rows: list[CensusRow] = []
    for demand in sorted(
        demands, key=lambda item: (item.strategy_id, item.symbol, item.capability.value)
    ):
        evidence = attempt_by_key.get((demand.symbol, demand.capability))
        if evidence is None:
            classification = (
                MissingnessClass.ACQUISITION_NOT_EXECUTED
                if diagnostics_complete
                else MissingnessClass.DIAGNOSTIC_GAP
            )
            rows.append(
                CensusRow(
                    demand.strategy_id,
                    demand.symbol,
                    demand.capability,
                    None,
                    classification,
                    MissingnessOwner.ASA,
                    classification.value,
                )
            )
            continue

        classification, owner, reason = _classify_attempt(evidence)
        latest_reason = reason_by_pair.get((demand.strategy_id, demand.symbol))
        if classification is MissingnessClass.CURRENT_USABLE and latest_reason:
            classification, owner = _classify_result_reason(latest_reason)
            reason = latest_reason
        rows.append(
            CensusRow(
                demand.strategy_id,
                demand.symbol,
                demand.capability,
                evidence.attempt.provider_id,
                classification,
                owner,
                reason,
            )
        )

    counts = Counter(f"{row.owner.value}:{row.classification.value}" for row in rows)
    return MissingnessCensus(tuple(rows), tuple(sorted(counts.items())))


def _classify_attempt(
    evidence: SubjectAttemptEvidence,
) -> tuple[MissingnessClass, MissingnessOwner, str]:
    code = evidence.attempt.diagnostic_code
    if code is None:
        return (
            MissingnessClass.CURRENT_USABLE,
            MissingnessOwner.NOT_APPLICABLE,
            "success",
        )
    if code is ProviderErrorCode.STALE_DATA:
        return MissingnessClass.STALE, MissingnessOwner.UNRESOLVED, code.value
    if code in {
        ProviderErrorCode.QUOTA_EXHAUSTED,
        ProviderErrorCode.PAIR_BUDGET_EXHAUSTED,
        ProviderErrorCode.PAIR_BURST_EXHAUSTED,
        ProviderErrorCode.PROVIDER_ROLLING_WINDOW_EXHAUSTED,
        ProviderErrorCode.PROVIDER_COOLDOWN_ACTIVE,
    }:
        return (
            MissingnessClass.ACQUISITION_NOT_EXECUTED,
            MissingnessOwner.ASA,
            code.value,
        )
    if code in {
        ProviderErrorCode.RATE_LIMITED,
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
        ProviderErrorCode.TRANSPORT_ERROR,
    }:
        return (
            MissingnessClass.PROVIDER_FAILURE,
            MissingnessOwner.PROVIDER_EXTERNAL,
            code.value,
        )
    if code in {
        ProviderErrorCode.ENTITLEMENT_MISSING,
        ProviderErrorCode.AUTHORIZATION_FAILED,
        ProviderErrorCode.UNSUPPORTED_CAPABILITY,
        ProviderErrorCode.UNSUPPORTED_SYMBOL,
    }:
        return (
            MissingnessClass.ENTITLEMENT_OR_COVERAGE,
            MissingnessOwner.PROVIDER_EXTERNAL,
            code.value,
        )
    if code in {ProviderErrorCode.NO_DATA, ProviderErrorCode.EMPTY_PAYLOAD}:
        owner = (
            MissingnessOwner.LEGITIMATELY_UNAVAILABLE
            if evidence.authoritative_absence_confirmed
            else MissingnessOwner.PROVIDER_EXTERNAL
        )
        classification = (
            MissingnessClass.GENUINELY_UNKNOWN_OR_UNANNOUNCED
            if evidence.authoritative_absence_confirmed
            else MissingnessClass.ENTITLEMENT_OR_COVERAGE
        )
        return classification, owner, code.value
    if code in {
        ProviderErrorCode.INVALID_REQUEST,
        ProviderErrorCode.SCHEMA_MISMATCH,
        ProviderErrorCode.INCOMPLETE_DATA,
        ProviderErrorCode.CONFIGURATION_ERROR,
        ProviderErrorCode.AUTHENTICATION_FAILED,
        ProviderErrorCode.UNKNOWN_PROVIDER_ERROR,
    }:
        return (
            MissingnessClass.IDENTITY_MAPPING_OR_CANONICALIZATION,
            MissingnessOwner.ASA,
            code.value,
        )
    return MissingnessClass.PROVIDER_FAILURE, MissingnessOwner.ASA, code.value


def _classify_result_reason(
    reason: str,
) -> tuple[MissingnessClass, MissingnessOwner]:
    normalized = reason.strip().lower()
    if normalized in {
        "insufficient_historical_bars",
        "insufficient_adjusted_history",
        "insufficient_total_return_history",
        "non_positive_forward_variance",
    }:
        return (
            MissingnessClass.DERIVATION_OR_INSUFFICIENT_HISTORY,
            MissingnessOwner.UNRESOLVED,
        )
    if normalized in {
        "no_future_expiration",
        "no_valid_expiration_pair",
        "selected_expiration_missing",
    }:
        return (
            MissingnessClass.TEMPORALLY_UNAVAILABLE,
            MissingnessOwner.LEGITIMATELY_UNAVAILABLE,
        )
    if normalized in {"missing_earnings_date", "unknown_earnings_date"}:
        return (
            MissingnessClass.GENUINELY_UNKNOWN_OR_UNANNOUNCED,
            MissingnessOwner.UNRESOLVED,
        )
    if normalized in {"subject_preparation_failed", "strategy_knowledge_construction_failed"}:
        return MissingnessClass.IDENTITY_MAPPING_OR_CANONICALIZATION, MissingnessOwner.ASA
    return MissingnessClass.DIAGNOSTIC_GAP, MissingnessOwner.ASA
