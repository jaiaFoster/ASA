from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from asa.application.portfolio_structures import project_option_structures
from asa.contracts.portfolio import OptionPositionLeg, OptionType, PositionSide
from asa.contracts.portfolio_structures import OptionStructureKind, UnmatchedLegReason


def _leg(
    *, kind: OptionType, strike: str, expiration: date, side: PositionSide
) -> OptionPositionLeg:
    return OptionPositionLeg(
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        underlying_symbol="AAPL",
        option_symbol=f"{kind.value}-{strike}-{expiration}-{side.value}",
        option_type=kind,
        strike=Decimal(strike),
        expiration=expiration,
        quantity=Decimal("1"),
        side=side,
        average_price=None,
        observed_at=datetime(2026, 8, 28, tzinfo=UTC),
        original_provider="fixture",
    )


def test_recognizes_calendar_without_changing_raw_legs() -> None:
    legs = (
        _leg(
            kind=OptionType.CALL,
            strike="200",
            expiration=date(2026, 9, 18),
            side=PositionSide.SHORT,
        ),
        _leg(
            kind=OptionType.CALL,
            strike="200",
            expiration=date(2026, 10, 16),
            side=PositionSide.LONG,
        ),
    )
    projection = project_option_structures(legs)
    assert projection.structures[0].kind == OptionStructureKind.CALENDAR
    assert set(projection.structures[0].legs) == set(legs)
    assert projection.unmatched_legs == ()


def test_recognizes_vertical() -> None:
    expiration = date(2026, 9, 18)
    projection = project_option_structures(
        (
            _leg(kind=OptionType.PUT, strike="180", expiration=expiration, side=PositionSide.LONG),
            _leg(kind=OptionType.PUT, strike="170", expiration=expiration, side=PositionSide.SHORT),
        )
    )
    assert projection.structures[0].kind == OptionStructureKind.VERTICAL


def test_recognizes_call_and_put_calendars_as_double_calendar() -> None:
    front, back = date(2026, 9, 18), date(2026, 10, 16)
    legs = tuple(
        _leg(kind=kind, strike=strike, expiration=expiration, side=side)
        for kind, strike in ((OptionType.CALL, "210"), (OptionType.PUT, "190"))
        for expiration, side in ((front, PositionSide.SHORT), (back, PositionSide.LONG))
    )
    projection = project_option_structures(reversed(legs))
    assert projection.structures[0].kind == OptionStructureKind.DOUBLE_CALENDAR
    assert set(projection.structures[0].legs) == set(legs)


def test_ambiguous_group_and_unequal_quantities_remain_unmatched() -> None:
    expiration = date(2026, 9, 18)
    three_legs = tuple(
        _leg(kind=OptionType.CALL, strike=strike, expiration=expiration, side=side)
        for strike, side in (
            ("190", PositionSide.LONG),
            ("200", PositionSide.SHORT),
            ("210", PositionSide.LONG),
        )
    )
    ambiguous = project_option_structures(three_legs)
    assert ambiguous.structures == ()
    assert {item.reason for item in ambiguous.unmatched_legs} == {
        UnmatchedLegReason.AMBIGUOUS_GROUPING
    }

    unequal = project_option_structures(
        (three_legs[0], replace(three_legs[1], quantity=Decimal("2")))
    )
    assert unequal.structures == ()
    assert {item.reason for item in unequal.unmatched_legs} == {
        UnmatchedLegReason.UNEQUAL_QUANTITIES
    }
