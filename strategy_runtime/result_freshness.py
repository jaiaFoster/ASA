"""Current projection of persisted screening-result freshness.

Persistence time never changes economic evidence time.  Persisted temporal
metadata records the decision made when a result was created; this module
re-evaluates only the read-time presentation against the current market
session, without rewriting the immutable stored result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar
from strategy_runtime.result import UniversalScreeningResult


@dataclass(frozen=True, slots=True)
class CurrentResultFreshness:
    age_seconds: int
    freshness_status: str
    display_freshness: str
    current_market_session: bool


def project_current_result_freshness(
    result: UniversalScreeningResult,
    *,
    as_of: datetime,
    fallback_threshold_seconds: int = 86_400,
    calendar: UsEquitySessionCalendar | None = None,
) -> CurrentResultFreshness:
    """Project current freshness from evidence time and session identity.

    A result with temporal metadata is display-fresh only when its evidence
    belongs to the current local trading session and its stored evidence
    quality was usable and fresh/live/delayed.  Prior-session evidence is never
    relabeled current merely because the row was persisted or read recently.
    """

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("project_current_result_freshness.as_of must be timezone-aware")
    temporal = result.temporal
    observed_at = temporal.observed_at if temporal is not None else result.observed_at
    age = max(0, int((as_of.astimezone(UTC) - observed_at.astimezone(UTC)).total_seconds()))
    if temporal is None:
        display = "fresh" if age <= fallback_threshold_seconds else "stale"
        return CurrentResultFreshness(age, display, display, False)

    session_calendar = calendar or UsEquitySessionCalendar()
    local_date = as_of.astimezone(NEW_YORK).date()
    session = session_calendar.session(local_date)
    current_session = (
        session is not None and temporal.market_session_date == session.trading_date
    )
    evidence_fresh = temporal.freshness_status in {"fresh", "live", "delayed"}
    evidence_usable = temporal.usability_status in {"usable", "usable_with_warning"}
    display = "fresh" if current_session and evidence_fresh and evidence_usable else "stale"
    status = temporal.freshness_status if display == "fresh" else "stale"
    return CurrentResultFreshness(age, status, display, current_session)
