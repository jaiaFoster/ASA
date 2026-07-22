from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from domain import ExpirationCycle, OptionType
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
            chain, expirations.cycles, fixtures.AS_OF_DATE, strike=Decimal("105")
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
            build_forward_factor_context(chain, too_short, fixtures.AS_OF_DATE, strike=Decimal("105"))


class TestBuildEarningsCalendarContext:
    def test_builds_a_context(self) -> None:
        front, back = fixtures.earnings_calendar_expirations()
        event = fixtures.earnings_calendar_event()
        chain = fixtures.earnings_calendar_chain()
        context = build_earnings_calendar_context(
            chain, event, front, back, fixtures.AS_OF_DATE, target_strike=Decimal("100")
        )
        values = dict(context.entries)
        assert values["calendar.target_strike"].value == Decimal("100")
        assert values["event_window.event"].value is event


class TestBuildSkewMomentumContext:
    def test_builds_a_context(self) -> None:
        chain = fixtures.skew_momentum_chain()
        context = build_skew_momentum_context(
            chain, fixtures.SKEW_EXPIRATION, strike=Decimal("100"), option_type=OptionType.CALL
        )
        values = dict(context.entries)
        assert values["vertical.expiration"].value == fixtures.SKEW_EXPIRATION
        assert values["liquidity.contract"].value.strike == Decimal("100")
