"""Earnings Calendar's own pure subject-planning declaration and phase-two
expansion (SPRINT-014 S14-PR-05A, Architect infrastructure checkpoint PASS
on 8c924e0 -- "proceed with the Earnings-specific increment"; revised
after the second checkpoint's Founder-approved bounded contract extension,
f1078c7, admitted collection-valued observations for OPTION_CHAIN_V1
expirations and HISTORICAL_BARS_V1).

Owns exactly what ADR-010 assigns to strategies/ in the subject-first
pipeline:

* the manifest-derived bootstrap ``CapabilityDemand`` declaration (phase
  one -- quote, earnings event, expiration discovery, and historical bars
  for realized volatility, covering exactly the four capabilities
  strategies.requirements.earnings_calendar_requirement() projects from
  the manifest);
* the pure phase-two expansion that selects an earnings-relative
  front/back expiration pair from phase-one evidence and declares the
  exact chain demands needed to acquire them;
* the pure, post-plan evidence-selection step a fact-consuming caller
  uses after phase two resolves.

Never imports screening/ or market_data/ (this module's own architecture
boundary, tests/architecture/test_strategy_boundaries.py, forbids both) --
every function here receives and returns only domain-owned types
(``CapabilityDemand``, ``ResolvedCapabilityEvidence``, ``DemandExpansion``,
``UnknownReason``), matching screening.subject_planning's own
``DemandExpansionFunction`` signature structurally without ever depending
on that module. Expiration-pair selection is invoked, not reimplemented,
through analytics.expiration_selection's existing pure selector, so this
module's own bounded scope reduces to *which* evidence to request and
*which* already-listed pair satisfies Earnings Calendar's manifest-owned
policy.

Deliberately excludes strike selection, richness, realized volatility, and
scoring: those formulas stay in analytics/ and are computed later, by
whatever strategy-owned step consumes the ``EarningsCalendarPhaseTwoEvidence``
this module's own post-plan selector returns (Architect checkpoint item 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Mapping  # noqa: UP035 -- collections.abc is outside strategies/' own boundary

from analytics.expiration_selection import (
    ExpirationCandidate,
    select_earnings_relative_expiration_pair,
)
from domain import (
    CapabilityDemand,
    DemandExpansion,
    EarningsEvent,
    EvidenceUsability,
    ExpirationCollection,
    MarketCapability,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from strategies.requirements import EarningsCalendarRequirement, earnings_calendar_requirement

DEFAULT_EARNINGS_CALENDAR_REQUIREMENT = earnings_calendar_requirement()

_QUOTE_REQUIRED_FIELDS = ("last",)
_EARNINGS_REQUIRED_FIELDS = ("earnings_date",)
_EXPIRATIONS_REQUIRED_FIELDS = ("expirations",)
_CHAIN_REQUIRED_FIELDS = ("contracts",)
_HISTORICAL_BARS_REQUIRED_FIELDS = ("close",)

# The one strategy-owned source for Earnings Calendar's own historical-
# bars lookback window (45 calendar days, ~30 trading days) used for
# realized-volatility computation -- not manifest-derived, since the
# manifest declares no historical-bars-specific parameter node. Public
# (Architect checkpoint, third review) so the still-live legacy adapter
# (screening/live_adapters.py's own build_live_earnings_calendar_adapter)
# consumes this same value during the S14-PR-05A transition instead of
# carrying an independently editable copy; deleting that legacy adapter
# later removes the only other reader, never this constant's own home.
HISTORICAL_LOOKBACK_DAYS = 45


@dataclass(frozen=True, slots=True)
class EarningsCalendarPhaseTwoEvidence:
    """The exact, typed, provider-blind evidence a downstream strategy-
    owned scoring/graph step needs once phase two has resolved -- never
    ``SubjectPlanResult.diagnostic_fulfillments`` (Architect checkpoint
    item 6). Carries the resolved evidence values themselves, never a
    computed richness/volatility/score -- that computation stays in
    analytics/ (item 7).

    ``expiration_discovery_evidence`` (added at the sixth-review
    checkpoint) is the exact ExpirationCollection evidence phase-two
    expansion itself selected the front/back pair from -- carried
    forward here so a downstream consumer never has to guess which of
    possibly several ExpirationCollection observations in a sealed
    snapshot belongs to this evaluation; it binds this evidence bundle to
    one specific, provenance-checkable demand_id.
    """

    spot_price_evidence: ResolvedCapabilityEvidence
    earnings_evidence: ResolvedCapabilityEvidence
    historical_bars_evidence: ResolvedCapabilityEvidence
    expiration_discovery_evidence: ResolvedCapabilityEvidence
    front_chain_evidence: ResolvedCapabilityEvidence
    back_chain_evidence: ResolvedCapabilityEvidence


def quote_demand(now: datetime) -> CapabilityDemand:
    return CapabilityDemand(MarketCapability.REAL_TIME_QUOTE_V1, _QUOTE_REQUIRED_FIELDS, now, now)


def earnings_demand(
    now: datetime,
    *,
    requirement: EarningsCalendarRequirement = DEFAULT_EARNINGS_CALENDAR_REQUIREMENT,
) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.EARNINGS_CALENDAR_V1,
        _EARNINGS_REQUIRED_FIELDS,
        now,
        now + timedelta(days=requirement.lookahead_days),
    )


def expirations_demand(now: datetime) -> CapabilityDemand:
    """Expiration discovery, independent of any one expiration's own
    contracts (SPRINT-014 S14-PR-05A, Founder-approved bounded contract
    extension, f1078c7): resolves to one ExpirationCollection observation
    -- market_data/tradier.py's own real chain endpoint has no unscoped
    "every expiration's contracts" request to make, so this must stay a
    dedicated ``("expirations",)`` demand, never the comprehensive-chain
    demand an earlier revision of this module used.
    """
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1, _EXPIRATIONS_REQUIRED_FIELDS, now, now
    )


def historical_bars_demand(now: datetime) -> CapabilityDemand:
    """Daily closes for realized-volatility computation (analytics/,
    never here) -- resolves to one OHLCVSeries observation covering the
    lookback window, matching the Earnings Calendar manifest's own
    HISTORICAL_BARS_V1 requirement that earlier revisions of this module
    omitted.

    ``maximum_age_seconds`` is set explicitly to the lookback window plus
    one day (SPRINT-014 S14-PR-05A, Architect checkpoint: twelfth review
    -- "a request-identity mismatch to fix, not acceptable shadow
    overhead"), matching screening/live_adapters.py's own
    _acquire_daily_closes() formula exactly: leaving this at the generic
    3600-second default (right for a near-real-time quote/chain, wrong
    for a 45-day daily-close series that does not go stale hour to hour)
    made the subject-first CapabilityRequest for this capability compare
    unequal to the legacy adapter's own request for the identical window,
    so PlanBackedFulfillment reuse would silently trigger a second live
    provider call for this one capability instead of sharing the plan's
    already-resolved result.
    """
    lookback_start = now - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
    return CapabilityDemand(
        MarketCapability.HISTORICAL_BARS_V1,
        _HISTORICAL_BARS_REQUIRED_FIELDS,
        lookback_start,
        now,
        maximum_age_seconds=int(timedelta(days=HISTORICAL_LOOKBACK_DAYS + 1).total_seconds()),
    )


def chain_demand_at(now: datetime, expiration: date) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1, _CHAIN_REQUIRED_FIELDS, now, now, expiration=expiration
    )


def earnings_calendar_bootstrap_demands(
    now: datetime,
    *,
    requirement: EarningsCalendarRequirement = DEFAULT_EARNINGS_CALENDAR_REQUIREMENT,
) -> tuple[CapabilityDemand, ...]:
    """The four demands Earnings Calendar's own phase-one evidence always
    needs, regardless of what phase two later selects -- one per
    capability ``requirement.capabilities`` (manifest-derived, never a
    second, independently maintained copy) declares. The quote and
    historical bars are not read by ``expand_earnings_calendar_demands``
    itself -- both are carried only for the post-plan fact-selection step
    (``select_earnings_calendar_phase_two_evidence``).

    Raises ``ValueError`` if the capabilities these four hardcoded demands
    declare ever stop matching ``requirement.capabilities`` exactly
    (Architect checkpoint item 8): a manifest change that adds, removes,
    or replaces a required capability must make this declaration loudly
    invalid, never silently stale.
    """
    demands = (
        quote_demand(now),
        earnings_demand(now, requirement=requirement),
        expirations_demand(now),
        historical_bars_demand(now),
    )
    declared = frozenset(demand.capability for demand in demands)
    required = frozenset(requirement.capabilities)
    if declared != required:
        raise ValueError(
            "earnings_calendar_bootstrap_demands declares "
            f"{sorted(item.value for item in declared)} but the manifest-derived requirement "
            f"needs {sorted(item.value for item in required)} -- update the hardcoded demand "
            "set in strategies/earnings_calendar_planning.py to match"
        )
    return demands


def _resolved_earnings_date(evidence: ResolvedCapabilityEvidence | None) -> date | None:
    if evidence is None or evidence.usability is not EvidenceUsability.RESOLVED:
        return None
    value = evidence.value
    if not isinstance(value, EarningsEvent):
        return None
    return value.earnings_date


def _expiration_candidates(
    evidence: ResolvedCapabilityEvidence | None, as_of: date
) -> tuple[ExpirationCandidate, ...]:
    if evidence is None or evidence.usability is not EvidenceUsability.RESOLVED:
        return ()
    value = evidence.value
    if not isinstance(value, ExpirationCollection):
        return ()
    return tuple(
        ExpirationCandidate(cycle.expiration_date, cycle.days_to_expiration)
        for cycle in value.cycles
        if cycle.expiration_date >= as_of
    )


def expand_earnings_calendar_demands(
    evidence: Mapping[str, ResolvedCapabilityEvidence],
    *,
    now: datetime,
    requirement: EarningsCalendarRequirement = DEFAULT_EARNINGS_CALENDAR_REQUIREMENT,
) -> DemandExpansion:
    """Earnings Calendar's own pure phase-two expansion
    (screening.subject_planning.DemandExpansionFunction's exact shape,
    satisfied structurally, with no import of that module). Deterministic
    regardless of ``evidence``'s own iteration/construction order: every
    lookup here is by explicit demand_id key, never by iterating
    ``evidence`` itself.

    Returns a typed ``UnknownReason`` (never raises) for each of the two
    expected non-exceptional outcomes: an unusable/missing earnings date,
    or no listed expiration pair satisfying the manifest's own DTE/gap
    policy -- both ordinary, typed data a caller must handle explicitly.
    """
    the_earnings_demand = earnings_demand(now, requirement=requirement)
    the_expirations_demand = expirations_demand(now)

    earnings_date = _resolved_earnings_date(evidence.get(the_earnings_demand.demand_id))
    if earnings_date is None:
        return DemandExpansion(
            unknown_reasons=(
                UnknownReason(
                    "missing_earnings_date", demand_ids=(the_earnings_demand.demand_id,)
                ),
            )
        )

    candidates = _expiration_candidates(
        evidence.get(the_expirations_demand.demand_id), now.date()
    )
    policy = requirement.expiration_policy
    selected = select_earnings_relative_expiration_pair(
        candidates,
        earnings_date,
        front_min_dte=policy.front_min_dte,
        front_max_dte=policy.front_max_dte,
        back_min_dte=policy.back_min_dte,
        back_max_dte=policy.back_max_dte,
        target_gap_days=policy.target_gap_days,
        gap_tolerance_days=policy.gap_tolerance_days,
    )
    if selected is None:
        return DemandExpansion(
            unknown_reasons=(
                UnknownReason(
                    "no_valid_expiration_pair",
                    demand_ids=(
                        the_earnings_demand.demand_id,
                        the_expirations_demand.demand_id,
                    ),
                ),
            )
        )

    front_candidate, back_candidate = selected
    front_demand = chain_demand_at(now, front_candidate.expiration_date)
    back_demand = chain_demand_at(now, back_candidate.expiration_date)

    return DemandExpansion(
        demands=(front_demand, back_demand),
        # Stable, normalized selection identities (Architect checkpoint
        # item 4): both the human-readable ISO expiration dates and the
        # exact demand_id a post-plan consumer looks projected_evidence up
        # by -- never a live domain object, never an index into some
        # externally-tracked ordering.
        selections=(
            ("front_expiration", front_candidate.expiration_date.isoformat()),
            ("back_expiration", back_candidate.expiration_date.isoformat()),
            ("front_demand_id", front_demand.demand_id),
            ("back_demand_id", back_demand.demand_id),
        ),
    )


def select_earnings_calendar_phase_two_evidence(
    projected_evidence: Mapping[str, ResolvedCapabilityEvidence],
    selections: Mapping[str, object],
    *,
    now: datetime,
    requirement: EarningsCalendarRequirement = DEFAULT_EARNINGS_CALENDAR_REQUIREMENT,
) -> EarningsCalendarPhaseTwoEvidence | UnknownReason:
    """The one function a downstream strategy-owned fact-selection step
    may call once phase two has resolved. Consumes only
    ``SubjectPlanResult.projected_evidence`` and a
    ``DemandExpansion.selections`` view (Architect checkpoint item 6) --
    never ``diagnostic_fulfillments``. Returns a typed ``UnknownReason``,
    never raises, when the expansion recorded no selection (phase two
    itself was unknown) or when any of the five required pieces of
    evidence is missing or was projected UNKNOWN -- an ordinary, expected
    outcome, not a defect.
    """
    front_demand_id = selections.get("front_demand_id")
    back_demand_id = selections.get("back_demand_id")
    if not isinstance(front_demand_id, str) or not isinstance(back_demand_id, str):
        return UnknownReason("missing_expiration_pair_selection")

    the_quote_demand_id = quote_demand(now).demand_id
    the_earnings_demand_id = earnings_demand(now, requirement=requirement).demand_id
    the_historical_bars_demand_id = historical_bars_demand(now).demand_id
    the_expirations_demand_id = expirations_demand(now).demand_id
    by_demand_id = {
        the_quote_demand_id: projected_evidence.get(the_quote_demand_id),
        the_earnings_demand_id: projected_evidence.get(the_earnings_demand_id),
        the_historical_bars_demand_id: projected_evidence.get(the_historical_bars_demand_id),
        the_expirations_demand_id: projected_evidence.get(the_expirations_demand_id),
        front_demand_id: projected_evidence.get(front_demand_id),
        back_demand_id: projected_evidence.get(back_demand_id),
    }
    unusable = tuple(
        demand_id
        for demand_id, item in by_demand_id.items()
        if item is None or item.usability is not EvidenceUsability.RESOLVED
    )
    if unusable:
        return UnknownReason("unusable_phase_two_evidence", demand_ids=unusable)

    return EarningsCalendarPhaseTwoEvidence(
        spot_price_evidence=by_demand_id[the_quote_demand_id],  # type: ignore[arg-type]
        earnings_evidence=by_demand_id[the_earnings_demand_id],  # type: ignore[arg-type]
        historical_bars_evidence=by_demand_id[  # type: ignore[arg-type]
            the_historical_bars_demand_id
        ],
        expiration_discovery_evidence=by_demand_id[  # type: ignore[arg-type]
            the_expirations_demand_id
        ],
        front_chain_evidence=by_demand_id[front_demand_id],  # type: ignore[arg-type]
        back_chain_evidence=by_demand_id[back_demand_id],  # type: ignore[arg-type]
    )
