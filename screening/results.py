"""Canonical screening result envelope (SCREEN-003)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from domain import EvidenceReference
from domain.market_data import CompletenessMetadata
from domain.values import require_tz_aware

_FAILURE_DETAIL_MAX_LENGTH = 500
ExplanationScalar = Decimal | int | bool | str | None


@dataclass(frozen=True, slots=True)
class ScreeningExplanation:
    """Immutable strategy-produced audit projection.

    Values are names from the canonical manifest outputs.  Screening transports
    them but never interprets their financial meaning.
    """

    canonical_facts: tuple[tuple[str, ExplanationScalar], ...] = ()
    named_derived_facts: tuple[tuple[str, ExplanationScalar], ...] = ()
    formula_versions: tuple[tuple[str, str], ...] = ()
    gate_results: tuple[tuple[str, bool | None], ...] = ()
    direction: str | None = None
    structure: str | None = None
    reason_codes: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "canonical_facts",
            "named_derived_facts",
            "formula_versions",
            "gate_results",
        ):
            entries = getattr(self, field_name)
            keys = tuple(key for key, _ in entries)
            if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                raise ValueError(
                    f"ScreeningExplanation.{field_name} must have unique sorted keys"
                )
        for value in (*self.reason_codes, *self.assumptions, *self.warnings):
            _normalized_text(value, "ScreeningExplanation", "entry")


class ScreeningOutcomeStatus(StrEnum):
    """The screening framework's own execution-level outcome for one
    strategy against one subject -- independent of the strategy's native
    signal classification, which is a separate field.
    """

    PASS = "pass"
    NO_SIGNAL = "no_signal"
    MISSING_DATA = "missing_data"
    MALFORMED_OUTPUT = "malformed_output"
    STRATEGY_EXCEPTION = "strategy_exception"


SUCCESS_OUTCOME_STATUSES = frozenset(
    {ScreeningOutcomeStatus.PASS, ScreeningOutcomeStatus.NO_SIGNAL}
)


def _normalized_text(value: str, owner: str, field_name: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{owner}.{field_name} must be non-empty normalized text")


def bounded_failure_detail(text: str) -> str:
    """Truncate free-form failure text to a fixed, bounded length.

    Callers remain responsible for redacting secrets or raw payloads before
    calling this -- it only bounds length, it does not scan content.
    """
    stripped = text.strip()
    if len(stripped) <= _FAILURE_DETAIL_MAX_LENGTH:
        return stripped
    return stripped[: _FAILURE_DETAIL_MAX_LENGTH - 3] + "..."


@dataclass(frozen=True, slots=True)
class ScreeningResult:
    """One immutable, canonically serializable screening result.

    ``signal_classification`` and ``strategy_native_score`` are populated
    only for a successful ``outcome_status`` (PASS or NO_SIGNAL);
    ``strategy_native_score`` stays None whenever the strategy defines no
    native score -- the framework never synthesizes one (SPRINT-006
    execution_rules).
    """

    run_id: str
    strategy_id: str
    strategy_version: str
    subject_identity: str
    as_of: datetime
    outcome_status: ScreeningOutcomeStatus
    signal_classification: str | None
    strategy_native_score: Decimal | None
    evidence: tuple[EvidenceReference, ...]
    input_provenance: tuple[EvidenceReference, ...]
    completeness: CompletenessMetadata | None
    failure_detail: str | None
    explanation: ScreeningExplanation | None = None

    def __post_init__(self) -> None:
        for name in ("run_id", "strategy_id", "strategy_version", "subject_identity"):
            _normalized_text(getattr(self, name), "ScreeningResult", name)
        require_tz_aware(self.as_of, "ScreeningResult", "as_of")

        is_success = self.outcome_status in SUCCESS_OUTCOME_STATUSES

        if is_success and self.failure_detail is not None:
            raise ValueError(
                "ScreeningResult must not carry failure_detail for a successful outcome_status"
            )
        if not is_success:
            if self.failure_detail is None:
                raise ValueError(
                    "ScreeningResult requires failure_detail for a non-success outcome_status"
                )
            if len(self.failure_detail) > _FAILURE_DETAIL_MAX_LENGTH:
                raise ValueError("ScreeningResult.failure_detail exceeds the bounded length")
            if self.signal_classification is not None:
                raise ValueError(
                    "ScreeningResult must not carry signal_classification for a "
                    "non-success outcome_status"
                )
            if self.strategy_native_score is not None:
                raise ValueError(
                    "ScreeningResult must not carry strategy_native_score for a "
                    "non-success outcome_status"
                )
            if self.explanation is not None:
                raise ValueError(
                    "ScreeningResult must not carry explanation for a non-success "
                    "outcome_status"
                )

        if (
            self.outcome_status is ScreeningOutcomeStatus.PASS
            and self.signal_classification is None
        ):
            raise ValueError(
                "ScreeningResult requires signal_classification for outcome_status PASS"
            )
        if self.signal_classification is not None:
            _normalized_text(self.signal_classification, "ScreeningResult", "signal_classification")
