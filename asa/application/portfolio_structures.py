from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from asa.contracts.portfolio import OptionPositionLeg, PositionSide
from asa.contracts.portfolio_structures import (
    OptionStructure,
    OptionStructureKind,
    OptionStructureProjection,
    UnmatchedLegReason,
    UnmatchedOptionLeg,
)


def project_option_structures(
    legs: Iterable[OptionPositionLeg],
) -> OptionStructureProjection:
    """Derive only unambiguous structures without modifying canonical legs."""
    grouped: dict[tuple[str, str], list[OptionPositionLeg]] = defaultdict(list)
    for leg in legs:
        grouped[(str(leg.account_id), leg.underlying_symbol)].append(leg)

    structures: list[OptionStructure] = []
    unmatched: list[UnmatchedOptionLeg] = []
    for key in sorted(grouped):
        group = tuple(sorted(grouped[key], key=_leg_order))
        structure, reason = _recognize_exact_group(group)
        if structure is not None:
            structures.append(structure)
        else:
            unmatched.extend(UnmatchedOptionLeg(leg=leg, reason=reason) for leg in group)
    return OptionStructureProjection(
        structures=tuple(structures),
        unmatched_legs=tuple(unmatched),
    )


def _recognize_exact_group(
    legs: tuple[OptionPositionLeg, ...],
) -> tuple[OptionStructure | None, UnmatchedLegReason]:
    quantities = {abs(leg.quantity) for leg in legs}
    if len(quantities) != 1 or quantities == {Decimal("0")}:
        return None, UnmatchedLegReason.UNEQUAL_QUANTITIES
    if len(legs) == 2:
        if _is_calendar(legs):
            return OptionStructure(
                OptionStructureKind.CALENDAR, legs
            ), UnmatchedLegReason.NO_SUPPORTED_STRUCTURE
        if _is_vertical(legs):
            return OptionStructure(
                OptionStructureKind.VERTICAL, legs
            ), UnmatchedLegReason.NO_SUPPORTED_STRUCTURE
        return None, UnmatchedLegReason.NO_SUPPORTED_STRUCTURE
    if len(legs) == 4 and _is_double_calendar(legs):
        return OptionStructure(
            OptionStructureKind.DOUBLE_CALENDAR, legs
        ), UnmatchedLegReason.NO_SUPPORTED_STRUCTURE
    if len(legs) > 2:
        return None, UnmatchedLegReason.AMBIGUOUS_GROUPING
    return None, UnmatchedLegReason.NO_SUPPORTED_STRUCTURE


def _opposite_sides(legs: tuple[OptionPositionLeg, ...]) -> bool:
    return {leg.side for leg in legs} == {PositionSide.LONG, PositionSide.SHORT}


def _is_calendar(legs: tuple[OptionPositionLeg, ...]) -> bool:
    if len(legs) != 2 or not _opposite_sides(legs):
        return False
    short = next(leg for leg in legs if leg.side == PositionSide.SHORT)
    long = next(leg for leg in legs if leg.side == PositionSide.LONG)
    return (
        short.option_type == long.option_type
        and short.strike == long.strike
        and short.expiration < long.expiration
    )


def _is_vertical(legs: tuple[OptionPositionLeg, ...]) -> bool:
    return (
        len(legs) == 2
        and _opposite_sides(legs)
        and len({leg.option_type for leg in legs}) == 1
        and len({leg.expiration for leg in legs}) == 1
        and len({leg.strike for leg in legs}) == 2
    )


def _is_double_calendar(legs: tuple[OptionPositionLeg, ...]) -> bool:
    if {leg.option_type.value for leg in legs} != {"call", "put"}:
        return False
    calendars = []
    for option_type in sorted({leg.option_type for leg in legs}, key=lambda item: item.value):
        pair = tuple(leg for leg in legs if leg.option_type == option_type)
        if not _is_calendar(pair):
            return False
        calendars.append(pair)
    front_back = {
        (
            next(leg.expiration for leg in pair if leg.side == PositionSide.SHORT),
            next(leg.expiration for leg in pair if leg.side == PositionSide.LONG),
        )
        for pair in calendars
    }
    return len(front_back) == 1


def _leg_order(leg: OptionPositionLeg) -> tuple[str, str, str, str]:
    return (
        leg.option_type.value,
        leg.expiration.isoformat(),
        str(leg.strike),
        leg.side.value,
    )
