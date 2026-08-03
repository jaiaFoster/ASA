from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from domain import ExpirationCycle, OptionChain, OptionType
from screening import fixtures
from screening.context_builders import (
    NoValidExpirationPairError,
    build_earnings_calendar_context,
    build_forward_factor_context,
    build_skew_momentum_context,
)


class TestBuildForwardFactorContext:
    def test_builds_a_context_with_analytics_derived_values(self) -> None:
        chain = fixtures.forward_factor_chain()
        expirations = fixtures.forward_factor_expirations()
        context = build_forward_factor_context(
            chain,
            expirations.cycles,
            fixtures.AS_OF_DATE,
            front_strike=Decimal("105"),
            back_strike=Decimal("105"),
            earnings_eligible=True,
        )
        values = dict(context.entries)
        assert values["forward_iv.front_iv"].value == Decimal("0.48")
        assert values["forward_iv.back_iv"].value == Decimal("0.4548992562461861547567860943472296")
        assert values["forward_iv.front_dte"].value == 61
        assert values["forward_iv.back_dte"].value == 91
        assert values["factor.front_iv"].value == Decimal("0.48")
        assert values["eligibility.earnings_eligible"].value is True
        assert values["eligibility.confirmed_earnings_date"].value is None

    def test_raises_when_no_pair_satisfies_the_dte_policy(self) -> None:
        chain = fixtures.forward_factor_chain()
        near_expiration = fixtures.AS_OF_DATE + timedelta(days=5)
        too_short = (
            ExpirationCycle(
                near_expiration, 5, True, False, fixtures.AS_OF_DATE, fixtures.EVIDENCE
            ),
        )
        with pytest.raises(NoValidExpirationPairError):
            build_forward_factor_context(
                chain,
                too_short,
                fixtures.AS_OF_DATE,
                front_strike=Decimal("105"),
                back_strike=Decimal("105"),
                earnings_eligible=True,
            )

    def test_looks_up_front_and_back_iv_at_their_own_distinct_strikes(self) -> None:
        # SPRINT-011-CLOSEOUT/CLOSE-001 regression: production NoMatchingContractError
        # for GS/NFLX -- the front expiration's ATM strike was reused verbatim to look
        # up the back expiration's IV too, and real back-month chains often don't list
        # the exact same strike as the front month. This chain has strike 105 at the
        # front expiration only and strike 110 at the back expiration only, proving
        # front_strike/back_strike are each looked up independently, not conflated.
        front_only_contract = fixtures.fixture_contract(
            "ff-front-only", fixtures.FORWARD_FRONT_EXPIRATION, "105", OptionType.CALL, "0.35", "2"
        )
        back_only_contract = fixtures.fixture_contract(
            "ff-back-only",
            fixtures.FORWARD_BACK_EXPIRATION,
            "110",
            OptionType.CALL,
            "0.38",
            "3",
            implied_volatility="0.40",
        )
        chain = OptionChain(
            "mismatched-strike-ladder",
            fixtures.fixture_security(),
            fixtures.OBSERVED_AT,
            (front_only_contract, back_only_contract),
            fixtures.EVIDENCE,
        )
        expirations = fixtures.forward_factor_expirations()
        context = build_forward_factor_context(
            chain,
            expirations.cycles,
            fixtures.AS_OF_DATE,
            front_strike=Decimal("105"),
            back_strike=Decimal("110"),
            earnings_eligible=True,
        )
        values = dict(context.entries)
        assert values["forward_iv.front_iv"].value == Decimal("0.30")  # fixture_contract default
        assert values["forward_iv.back_iv"].value == Decimal("0.40")


class TestBuildEarningsCalendarContext:
    def test_builds_a_context(self) -> None:
        front, back = fixtures.earnings_calendar_expirations()
        event = fixtures.earnings_calendar_event()
        chain = fixtures.earnings_calendar_chain()
        context = build_earnings_calendar_context(
            chain,
            event,
            front,
            back,
            fixtures.AS_OF_DATE,
            target_strike=Decimal("100"),
            term_structure_richness=Decimal("80"),
            iv_realized_volatility_richness=Decimal("60"),
        )
        values = dict(context.entries)
        assert values["calendar.target_strike"].value == Decimal("100")
        assert values["event_window.event"].value is event
        assert values["score.primary"].value == Decimal("80")
        assert values["score.secondary"].value == Decimal("60")


class TestBuildSkewMomentumContext:
    def test_builds_a_context(self) -> None:
        chain = fixtures.skew_momentum_chain()
        context = build_skew_momentum_context(
            chain,
            fixtures.SKEW_EXPIRATION,
            normalized_call_skew=Decimal("0.5"),
            normalized_put_skew=Decimal("0.2"),
            call_skew_zscore=Decimal("-2.1"),
            put_skew_zscore=Decimal("-1"),
            historical_valid_observations=60,
            call_atm_iv_minus_rv=Decimal("-0.01"),
            put_atm_iv_minus_rv=Decimal("0.01"),
            call_wing_iv_minus_rv=Decimal("0.09"),
            put_wing_iv_minus_rv=Decimal("0.07"),
            call_wing_iv_minus_atm_iv=Decimal("0.1"),
            put_wing_iv_minus_atm_iv=Decimal("0.06"),
            time_series_return=Decimal("0.05"),
            cross_sectional_percentile=Decimal("0.8"),
            comparison_peer_count=5,
            sector_relative_return=Decimal("-0.01"),
        )
        values = dict(context.entries)
        assert values["decision.expiration"].value == fixtures.SKEW_EXPIRATION
        assert values["decision.historical_valid_observations"].value == 60
        assert values["decision.comparison_peer_count"].value == 5
        assert values["decision.call_skew_zscore"].value == Decimal("-2.1")
