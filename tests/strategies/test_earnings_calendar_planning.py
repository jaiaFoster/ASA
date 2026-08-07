"""SPRINT-014 S14-PR-05A, Earnings-specific increment (Architect
infrastructure checkpoint PASS on 8c924e0): Earnings Calendar's own pure
subject-planning declaration and phase-two expansion.

Every evidence value here is synthetic, constructed directly against
domain.ResolvedCapabilityEvidence -- this module proves
strategies/earnings_calendar_planning.py's own pure logic in isolation,
never against a real provider, screening/, or market_data/ (this
increment's own explicit boundary).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from domain import (
    AnnouncementTime,
    EarningsEvent,
    EvidenceKind,
    EvidenceReference,
    EvidenceUsability,
    FreshnessStatus,
    MarketCapability,
    OptionChain,
    Quote,
    ResolvedCapabilityEvidence,
    UnknownReason,
)
from domain.market_data import MarketObservationValue
from strategies.earnings_calendar_planning import (
    DEFAULT_EARNINGS_CALENDAR_REQUIREMENT,
    EarningsCalendarPhaseTwoEvidence,
    bootstrap_chain_demand,
    chain_demand_at,
    earnings_calendar_bootstrap_demands,
    earnings_demand,
    expand_earnings_calendar_demands,
    quote_demand,
    select_earnings_calendar_phase_two_evidence,
)
from tests.domain.test_financial_contracts import option, security

NOW = datetime(2026, 8, 6, 15, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "instrument-reference:AAPL"),)

# Within EarningsCalendarExpirationPolicy's own default window (front 7-21
# DTE, back 22-75 DTE, target 30-day gap): an earnings date on 2026-08-20,
# a front expiration on 2026-08-14 (8 DTE, before earnings), a back
# expiration on 2026-09-18 (43 DTE, 35-day gap from front).
EARNINGS_DATE = date(2026, 8, 20)
FRONT_EXPIRATION = date(2026, 8, 14)
BACK_EXPIRATION = date(2026, 9, 18)


def _earnings_event(earnings_date: date = EARNINGS_DATE) -> EarningsEvent:
    return EarningsEvent(
        "earnings-1",
        security(),
        earnings_date,
        AnnouncementTime.AFTER_CLOSE,
        Decimal("0.05"),
        True,
        (),
        NOW,
        EVIDENCE,
    )


def _chain(*expirations: date) -> OptionChain:
    underlying = security()
    contracts = tuple(
        option(
            expiration=expiration, observed_at=NOW, underlying=underlying, suffix=str(index)
        )
        for index, expiration in enumerate(expirations)
    )
    return OptionChain("chain-1", underlying, NOW, contracts, EVIDENCE)


def _quote() -> Quote:
    return Quote(security().instrument, None, None, Decimal("189.15"), None, None, None, "USD")


def _resolved(
    demand_id: str, capability: MarketCapability, value: MarketObservationValue
) -> ResolvedCapabilityEvidence:
    return ResolvedCapabilityEvidence(
        demand_id, capability, EvidenceUsability.RESOLVED, value, ("obs-1",), FreshnessStatus.FRESH
    )


def _unknown(demand_id: str, capability: MarketCapability) -> ResolvedCapabilityEvidence:
    return ResolvedCapabilityEvidence(
        demand_id, capability, EvidenceUsability.UNKNOWN, None, (), None
    )


def _phase_one_evidence(
    *, earnings_date: date | None = EARNINGS_DATE, expirations: tuple[date, ...] = ()
) -> dict[str, ResolvedCapabilityEvidence]:
    earnings_id = earnings_demand(NOW).demand_id
    chain_id = bootstrap_chain_demand(NOW).demand_id
    evidence: dict[str, ResolvedCapabilityEvidence] = {}
    if earnings_date is not None:
        evidence[earnings_id] = _resolved(
            earnings_id, MarketCapability.EARNINGS_CALENDAR_V1, _earnings_event(earnings_date)
        )
    if expirations:
        evidence[chain_id] = _resolved(
            chain_id, MarketCapability.OPTION_CHAIN_V1, _chain(*expirations)
        )
    return evidence


class TestBootstrapDemands:
    def test_three_demands_have_distinct_capabilities(self) -> None:
        demands = earnings_calendar_bootstrap_demands(NOW)
        assert len(demands) == 3
        assert {demand.capability for demand in demands} == {
            MarketCapability.REAL_TIME_QUOTE_V1,
            MarketCapability.EARNINGS_CALENDAR_V1,
            MarketCapability.OPTION_CHAIN_V1,
        }

    def test_deterministic_across_calls(self) -> None:
        first = tuple(demand.demand_id for demand in earnings_calendar_bootstrap_demands(NOW))
        second = tuple(demand.demand_id for demand in earnings_calendar_bootstrap_demands(NOW))
        assert first == second

    def test_earnings_demand_window_matches_lookahead_days(self) -> None:
        demand = earnings_demand(NOW)
        assert demand.effective_end == NOW + timedelta(
            days=DEFAULT_EARNINGS_CALENDAR_REQUIREMENT.lookahead_days
        )

    def test_bootstrap_chain_demand_is_expiration_unscoped(self) -> None:
        assert bootstrap_chain_demand(NOW).expiration is None

    def test_chain_demand_at_is_scoped_to_one_expiration(self) -> None:
        demand = chain_demand_at(NOW, FRONT_EXPIRATION)
        assert demand.expiration == FRONT_EXPIRATION
        assert demand.demand_id != bootstrap_chain_demand(NOW).demand_id


class TestExpandEarningsCalendarDemands:
    def test_missing_earnings_evidence_is_unknown(self) -> None:
        evidence = _phase_one_evidence(earnings_date=None, expirations=(FRONT_EXPIRATION,))
        expansion = expand_earnings_calendar_demands(evidence, now=NOW)
        assert expansion.demands == ()
        assert len(expansion.unknown_reasons) == 1
        assert expansion.unknown_reasons[0].code == "missing_earnings_date"

    def test_unusable_earnings_evidence_is_unknown(self) -> None:
        earnings_id = earnings_demand(NOW).demand_id
        evidence = {
            earnings_id: _unknown(earnings_id, MarketCapability.EARNINGS_CALENDAR_V1)
        }
        expansion = expand_earnings_calendar_demands(evidence, now=NOW)
        assert expansion.unknown_reasons[0].code == "missing_earnings_date"
        assert expansion.unknown_reasons[0].demand_ids == (earnings_id,)

    def test_no_valid_expiration_pair_is_unknown(self) -> None:
        # Earnings resolved, but the chain lists nothing in the required
        # front/back DTE windows at all.
        evidence = _phase_one_evidence(expirations=(NOW.date() + timedelta(days=200),))
        expansion = expand_earnings_calendar_demands(evidence, now=NOW)
        assert expansion.demands == ()
        assert len(expansion.unknown_reasons) == 1
        assert expansion.unknown_reasons[0].code == "no_valid_expiration_pair"

    def test_no_listed_expirations_is_no_valid_pair_unknown(self) -> None:
        evidence = _phase_one_evidence(expirations=())
        expansion = expand_earnings_calendar_demands(evidence, now=NOW)
        assert expansion.unknown_reasons[0].code == "no_valid_expiration_pair"

    def test_valid_pair_produces_front_and_back_chain_demands(self) -> None:
        evidence = _phase_one_evidence(expirations=(FRONT_EXPIRATION, BACK_EXPIRATION))
        expansion = expand_earnings_calendar_demands(evidence, now=NOW)
        assert expansion.unknown_reasons == ()
        assert len(expansion.demands) == 2
        expirations = {demand.expiration for demand in expansion.demands}
        assert expirations == {FRONT_EXPIRATION, BACK_EXPIRATION}
        assert all(demand.required_fields == ("contracts",) for demand in expansion.demands)

    def test_valid_pair_selections_carry_stable_normalized_identities(self) -> None:
        evidence = _phase_one_evidence(expirations=(FRONT_EXPIRATION, BACK_EXPIRATION))
        expansion = expand_earnings_calendar_demands(evidence, now=NOW)
        selections = dict(expansion.selections)
        assert selections["front_expiration"] == FRONT_EXPIRATION.isoformat()
        assert selections["back_expiration"] == BACK_EXPIRATION.isoformat()
        assert selections["front_demand_id"] == chain_demand_at(NOW, FRONT_EXPIRATION).demand_id
        assert selections["back_demand_id"] == chain_demand_at(NOW, BACK_EXPIRATION).demand_id

    def test_extra_unrelated_expirations_do_not_change_the_selected_pair(self) -> None:
        # A distractor expiration far outside any policy window must not
        # change which pair is selected.
        far_future = NOW.date() + timedelta(days=400)
        with_distractor = _phase_one_evidence(
            expirations=(FRONT_EXPIRATION, BACK_EXPIRATION, far_future)
        )
        without_distractor = _phase_one_evidence(expirations=(FRONT_EXPIRATION, BACK_EXPIRATION))
        with_result = expand_earnings_calendar_demands(with_distractor, now=NOW)
        without_result = expand_earnings_calendar_demands(without_distractor, now=NOW)
        assert with_result.selections == without_result.selections

    def test_deterministic_output_regardless_of_evidence_mapping_order(self) -> None:
        forward = _phase_one_evidence(expirations=(FRONT_EXPIRATION, BACK_EXPIRATION))
        # Same content, reversed insertion order -- dict key lookup by
        # explicit demand_id must not depend on iteration/construction
        # order.
        backward = dict(reversed(list(forward.items())))
        forward_expansion = expand_earnings_calendar_demands(forward, now=NOW)
        backward_expansion = expand_earnings_calendar_demands(backward, now=NOW)
        assert forward_expansion.demands == backward_expansion.demands
        assert forward_expansion.selections == backward_expansion.selections


class TestSelectEarningsCalendarPhaseTwoEvidence:
    def _selections(self) -> dict[str, str]:
        front = chain_demand_at(NOW, FRONT_EXPIRATION)
        back = chain_demand_at(NOW, BACK_EXPIRATION)
        return {"front_demand_id": front.demand_id, "back_demand_id": back.demand_id}

    def test_missing_selection_is_unknown(self) -> None:
        result = select_earnings_calendar_phase_two_evidence({}, {}, now=NOW)
        assert isinstance(result, UnknownReason)
        assert result.code == "missing_expiration_pair_selection"

    def test_unusable_front_chain_evidence_is_unknown(self) -> None:
        selections = self._selections()
        front_id = selections["front_demand_id"]
        back_id = selections["back_demand_id"]
        earnings_id = earnings_demand(NOW).demand_id
        the_quote_id = quote_demand(NOW).demand_id
        projected = {
            the_quote_id: _resolved(the_quote_id, MarketCapability.REAL_TIME_QUOTE_V1, _quote()),
            earnings_id: _resolved(
                earnings_id, MarketCapability.EARNINGS_CALENDAR_V1, _earnings_event()
            ),
            front_id: _unknown(front_id, MarketCapability.OPTION_CHAIN_V1),
            back_id: _resolved(
                back_id, MarketCapability.OPTION_CHAIN_V1, _chain(BACK_EXPIRATION)
            ),
        }
        result = select_earnings_calendar_phase_two_evidence(projected, selections, now=NOW)
        assert isinstance(result, UnknownReason)
        assert result.code == "unusable_phase_two_evidence"
        assert front_id in result.demand_ids

    def test_missing_quote_evidence_is_unknown(self) -> None:
        selections = self._selections()
        front_id = selections["front_demand_id"]
        back_id = selections["back_demand_id"]
        earnings_id = earnings_demand(NOW).demand_id
        projected = {
            earnings_id: _resolved(
                earnings_id, MarketCapability.EARNINGS_CALENDAR_V1, _earnings_event()
            ),
            front_id: _resolved(
                front_id, MarketCapability.OPTION_CHAIN_V1, _chain(FRONT_EXPIRATION)
            ),
            back_id: _resolved(
                back_id, MarketCapability.OPTION_CHAIN_V1, _chain(BACK_EXPIRATION)
            ),
        }
        result = select_earnings_calendar_phase_two_evidence(projected, selections, now=NOW)
        assert isinstance(result, UnknownReason)
        assert result.code == "unusable_phase_two_evidence"

    def test_all_resolved_returns_typed_phase_two_evidence(self) -> None:
        selections = self._selections()
        front_id = selections["front_demand_id"]
        back_id = selections["back_demand_id"]
        earnings_id = earnings_demand(NOW).demand_id
        the_quote_id = quote_demand(NOW).demand_id
        projected = {
            the_quote_id: _resolved(the_quote_id, MarketCapability.REAL_TIME_QUOTE_V1, _quote()),
            earnings_id: _resolved(
                earnings_id, MarketCapability.EARNINGS_CALENDAR_V1, _earnings_event()
            ),
            front_id: _resolved(
                front_id, MarketCapability.OPTION_CHAIN_V1, _chain(FRONT_EXPIRATION)
            ),
            back_id: _resolved(
                back_id, MarketCapability.OPTION_CHAIN_V1, _chain(BACK_EXPIRATION)
            ),
        }
        result = select_earnings_calendar_phase_two_evidence(projected, selections, now=NOW)
        assert isinstance(result, EarningsCalendarPhaseTwoEvidence)
        assert result.spot_price_evidence.demand_id == the_quote_id
        assert result.earnings_evidence.demand_id == earnings_id
        assert result.front_chain_evidence.demand_id == front_id
        assert result.back_chain_evidence.demand_id == back_id

    def test_never_reads_diagnostic_style_input(self) -> None:
        """Structural guarantee: this function's own signature accepts
        only projected_evidence and selections -- there is no third
        parameter through which a caller could hand it
        SubjectPlanResult.diagnostic_fulfillments instead.
        """
        import inspect

        parameters = inspect.signature(select_earnings_calendar_phase_two_evidence).parameters
        assert set(parameters) == {"projected_evidence", "selections", "now", "requirement"}
