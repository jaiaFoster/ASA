"""Canonical screening result envelope (SCREEN-003)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from domain import EvidenceReference
from domain.market_data import CompletenessMetadata
from domain.values import require_tz_aware

_FAILURE_DETAIL_MAX_LENGTH = 500


class ScreeningOutcomeStatus(str, Enum):
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

        if self.outcome_status is ScreeningOutcomeStatus.PASS and self.signal_classification is None:
            raise ValueError("ScreeningResult requires signal_classification for outcome_status PASS")
        if self.signal_classification is not None:
            _normalized_text(self.signal_classification, "ScreeningResult", "signal_classification")
