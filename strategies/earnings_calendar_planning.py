"""Earnings Calendar's own pure subject-planning declaration and phase-two
expansion (SPRINT-014 S14-PR-05A, Architect infrastructure checkpoint PASS
on 8c924e0 -- "proceed with the Earnings-specific increment").

Owns exactly what ADR-010 assigns to strategies/ in the subject-first
pipeline:

* the manifest-derived bootstrap ``CapabilityDemand`` declaration (phase
  one -- quote, earnings event, and a comprehensive option chain wide
  enough to discover every listed expiration from its own contracts);
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
    MarketCapability,
    OptionChain,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from strategies.requirements import EarningsCalendarRequirement, earnings_calendar_requirement

DEFAULT_EARNINGS_CALENDAR_REQUIREMENT = earnings_calendar_requirement()

_QUOTE_REQUIRED_FIELDS = ("last",)
_EARNINGS_REQUIRED_FIELDS = ("earnings_date",)
_CHAIN_REQUIRED_FIELDS = ("contracts",)


@dataclass(frozen=True, slots=True)
class EarningsCalendarPhaseTwoEvidence:
    """The exact, typed, provider-blind evidence a downstream strategy-
    owned scoring/graph step needs once phase two has resolved -- never
    ``SubjectPlanResult.diagnostic_fulfillments`` (Architect checkpoint
    item 6). Carries the resolved evidence values themselves, never a
    computed richness/volatility/score -- that computation stays in
    analytics/ (item 7).
    """

    spot_price_evidence: ResolvedCapabilityEvidence
    earnings_evidence: ResolvedCapabilityEvidence
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


def bootstrap_chain_demand(now: datetime) -> CapabilityDemand:
    """A comprehensive, expiration-unscoped chain request -- expirations
    are discovered locally from its own returned contracts (the same,
    established technique screening.live_context.expirations_from_chain
    already uses for a provider that does not distinguish an expirations-
    only request from a full chain request), so this module never needs a
    second, multi-observation-per-demand capability shape the generic
    single-observation-per-demand planner (screening.subject_planning._project)
    cannot represent.
    """
    return CapabilityDemand(MarketCapability.OPTION_CHAIN_V1, _CHAIN_REQUIRED_FIELDS, now, now)


def chain_demand_at(now: datetime, expiration: date) -> CapabilityDemand:
    return CapabilityDemand(
        MarketCapability.OPTION_CHAIN_V1, _CHAIN_REQUIRED_FIELDS, now, now, expiration=expiration
    )


def earnings_calendar_bootstrap_demands(
    now: datetime,
    *,
    requirement: EarningsCalendarRequirement = DEFAULT_EARNINGS_CALENDAR_REQUIREMENT,
) -> tuple[CapabilityDemand, ...]:
    """The three demands Earnings Calendar's own phase-one evidence
    always needs, regardless of what phase two later selects. The quote
    is not read by ``expand_earnings_calendar_demands`` itself -- it is
    carried only for the post-plan fact-selection step
    (``select_earnings_calendar_phase_two_evidence``), which needs a spot
    price alongside the front/back chains.
    """
    return (
        quote_demand(now),
        earnings_demand(now, requirement=requirement),
        bootstrap_chain_demand(now),
    )


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
    if not isinstance(value, OptionChain):
        return ()
    unique_dates = sorted({contract.expiration for contract in value.contracts})
    return tuple(
        ExpirationCandidate(expiration, (expiration - as_of).days)
        for expiration in unique_dates
        if expiration >= as_of
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
    the_chain_demand = bootstrap_chain_demand(now)

    earnings_date = _resolved_earnings_date(evidence.get(the_earnings_demand.demand_id))
    if earnings_date is None:
        return DemandExpansion(
            unknown_reasons=(
                UnknownReason(
                    "missing_earnings_date", demand_ids=(the_earnings_demand.demand_id,)
                ),
            )
        )

    candidates = _expiration_candidates(evidence.get(the_chain_demand.demand_id), now.date())
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
                    demand_ids=(the_earnings_demand.demand_id, the_chain_demand.demand_id),
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
    itself was unknown) or when any of the four required pieces of
    evidence is missing or was projected UNKNOWN -- an ordinary, expected
    outcome, not a defect.
    """
    front_demand_id = selections.get("front_demand_id")
    back_demand_id = selections.get("back_demand_id")
    if not isinstance(front_demand_id, str) or not isinstance(back_demand_id, str):
        return UnknownReason("missing_expiration_pair_selection")

    the_quote_demand_id = quote_demand(now).demand_id
    the_earnings_demand_id = earnings_demand(now, requirement=requirement).demand_id
    by_demand_id = {
        the_quote_demand_id: projected_evidence.get(the_quote_demand_id),
        the_earnings_demand_id: projected_evidence.get(the_earnings_demand_id),
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
        front_chain_evidence=by_demand_id[front_demand_id],  # type: ignore[arg-type]
        back_chain_evidence=by_demand_id[back_demand_id],  # type: ignore[arg-type]
    )
