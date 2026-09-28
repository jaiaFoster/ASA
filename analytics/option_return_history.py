"""A17 monthly option-return history derived from sealed A08 evidence."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain import UnknownReason

FORMULA_ID = "DF-STRADDLE-MOMENTUM-FORMATION"
FORMULA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class MonthlyOptionReturn:
    formation_month: date
    return_value: Decimal
    source_panel_identity: str
    source_position_identity: str

    def __post_init__(self) -> None:
        if self.formation_month.day != 1:
            raise ValueError("formation_month must be normalized to month start")
        if not self.return_value.is_finite():
            raise ValueError("monthly option return must be finite")
        if not self.source_panel_identity or not self.source_position_identity:
            raise ValueError("monthly option return lineage is required")

    @property
    def identity(self) -> str:
        payload = (
            FORMULA_ID,
            FORMULA_VERSION,
            self.formation_month.isoformat(),
            str(self.return_value),
            self.source_panel_identity,
            self.source_position_identity,
        )
        return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def straddle_momentum_formation(
    history_by_lag: dict[int, MonthlyOptionReturn],
) -> Decimal | UnknownReason:
    """Heston formation signal: simple mean of complete lags 2..12; lag 1 skipped."""
    required = tuple(range(2, 13))
    missing = tuple(lag for lag in required if lag not in history_by_lag)
    if missing:
        return UnknownReason("insufficient_straddle_return_history")
    return sum((history_by_lag[lag].return_value for lag in required), Decimal(0)) / Decimal(11)
