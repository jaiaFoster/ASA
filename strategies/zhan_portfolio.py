"""Strategy-owned immutable Zhan subject candidate contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from domain import OptionContract, SecurityType


@dataclass(frozen=True, slots=True)
class ZhanSubjectCandidate:
    subject: str
    as_of: datetime
    evidence_identity: str
    spot: Decimal | None
    security_type: SecurityType | None
    shares_outstanding: Decimal | None
    risk_free_rate: Decimal | None
    negative_log_price: Decimal | None
    contracts: tuple[OptionContract, ...]
    formation_date_state: str
