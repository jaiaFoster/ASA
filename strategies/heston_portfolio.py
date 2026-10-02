"""Strategy-owned immutable Heston subject candidate."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from domain import OptionContract, UnknownReason


@dataclass(frozen=True, slots=True)
class HestonSubjectCandidate:
    subject: str
    as_of: datetime
    evidence_identity: str
    contracts: tuple[OptionContract, ...]
    selected_expiration: date
    formation_momentum: Decimal | UnknownReason
    formation_date_state: str
