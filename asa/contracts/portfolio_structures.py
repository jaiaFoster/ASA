from dataclasses import dataclass
from enum import StrEnum

from asa.contracts.portfolio import OptionPositionLeg


class OptionStructureKind(StrEnum):
    CALENDAR = "calendar"
    DOUBLE_CALENDAR = "double_calendar"
    VERTICAL = "vertical"


class UnmatchedLegReason(StrEnum):
    NO_SUPPORTED_STRUCTURE = "no_supported_structure"
    AMBIGUOUS_GROUPING = "ambiguous_grouping"
    UNEQUAL_QUANTITIES = "unequal_quantities"


@dataclass(frozen=True, slots=True)
class OptionStructure:
    kind: OptionStructureKind
    legs: tuple[OptionPositionLeg, ...]


@dataclass(frozen=True, slots=True)
class UnmatchedOptionLeg:
    leg: OptionPositionLeg
    reason: UnmatchedLegReason


@dataclass(frozen=True, slots=True)
class OptionStructureProjection:
    structures: tuple[OptionStructure, ...]
    unmatched_legs: tuple[UnmatchedOptionLeg, ...]
