"""Canonical freshness-to-usability policy, independent of providers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain import FreshnessMetadata, FreshnessStatus


class UsabilityStatus(StrEnum):
    USABLE = "usable"
    USABLE_WITH_WARNING = "usable_with_warning"
    REJECTED = "rejected"


class TemporalWarningCode(StrEnum):
    DELAYED_DATA = "delayed_data"
    PRIOR_SESSION_DATA = "prior_session_data"


@dataclass(frozen=True, slots=True)
class FreshnessRequirement:
    require_open_session: bool = False
    allow_prior_session: bool = True
    maximum_age_seconds: int | None = None
    maximum_input_skew_seconds: int | None = None

    def __post_init__(self) -> None:
        for name in ("maximum_age_seconds", "maximum_input_skew_seconds"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"FreshnessRequirement.{name} must be non-negative")


DEFAULT_FRESHNESS_REQUIREMENT = FreshnessRequirement()


@dataclass(frozen=True, slots=True)
class TemporalUsabilityDecision:
    status: UsabilityStatus
    reason: str
    warning_codes: tuple[TemporalWarningCode, ...] = ()


def evaluate_temporal_usability(
    freshness: FreshnessMetadata,
    requirement: FreshnessRequirement = DEFAULT_FRESHNESS_REQUIREMENT,
    *,
    market_is_open: bool,
) -> TemporalUsabilityDecision:
    if requirement.require_open_session and not market_is_open:
        return TemporalUsabilityDecision(
            UsabilityStatus.REJECTED, "strategy requires an open market session"
        )
    if (
        requirement.maximum_age_seconds is not None
        and freshness.age_seconds > requirement.maximum_age_seconds
        and freshness.status is not FreshnessStatus.PRIOR_SESSION
    ):
        return TemporalUsabilityDecision(
            UsabilityStatus.REJECTED, "observation exceeds strategy maximum age"
        )
    if freshness.status is FreshnessStatus.PRIOR_SESSION:
        if not requirement.allow_prior_session:
            return TemporalUsabilityDecision(
                UsabilityStatus.REJECTED, "strategy rejects prior-session observations"
            )
        return TemporalUsabilityDecision(
            UsabilityStatus.USABLE_WITH_WARNING,
            "latest verified observation is from the prior completed session",
            (TemporalWarningCode.PRIOR_SESSION_DATA,),
        )
    if freshness.status is FreshnessStatus.FRESH:
        return TemporalUsabilityDecision(UsabilityStatus.USABLE, "observation is current")
    return TemporalUsabilityDecision(
        UsabilityStatus.REJECTED, "observation freshness is unusable"
    )
