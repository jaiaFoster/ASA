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
        )
        values = dict(context.entries)
        assert values["forward_iv.front_iv"].value == Decimal("0.48")
        assert values["forward_iv.back_iv"].value == Decimal("0.4548992562461861547567860943472296")
        assert values["forward_iv.front_dte"].value == 61
        assert values["forward_iv.back_dte"].value == 91
        assert values["factor.front_ex_earnings_iv"].value == Decimal("0.48")

    def test_raises_when_no_pair_satisfies_the_dte_policy(self) -> None:
        chain = fixtures.forward_factor_chain()
        near_expiration = fixtures.AS_OF_DATE + timedelta(days=5)
        too_short = (
            ExpirationCycle(near_expiration, 5, True, False, fixtures.AS_OF_DATE, fixtures.EVIDENCE),
        )
        with pytest.raises(NoValidExpirationPairError):
            build_forward_factor_context(
                chain,
                too_short,
                fixtures.AS_OF_DATE,
                front_strike=Decimal("105"),
                back_strike=Decimal("105"),
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
            score_values=(Decimal("80"), Decimal("60")),
        )
        values = dict(context.entries)
        assert values["calendar.target_strike"].value == Decimal("100")
        assert values["event_window.event"].value is event
        assert values["score.values"].value == (Decimal("80"), Decimal("60"))


class TestBuildSkewMomentumContext:
    def test_builds_a_context(self) -> None:
        chain = fixtures.skew_momentum_chain()
        context = build_skew_momentum_context(
            chain,
            fixtures.SKEW_EXPIRATION,
            strike=Decimal("100"),
            option_type=OptionType.CALL,
            score_values=(Decimal("80"), Decimal("70")),
        )
        values = dict(context.entries)
        assert values["vertical.expiration"].value == fixtures.SKEW_EXPIRATION
        assert values["liquidity.contract"].value.strike == Decimal("100")
        assert values["score.values"].value == (Decimal("80"), Decimal("70"))
