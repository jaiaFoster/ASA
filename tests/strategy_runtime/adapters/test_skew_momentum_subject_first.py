from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from domain import OptionChain, UnknownReason
from strategy_runtime.adapters.skew_momentum_subject_first import _select_atm_strikes


class _PutOnlyChain:
    def find(self, **criteria: object) -> tuple[object, ...]:
        del criteria
        return ()


def test_no_calls_at_selected_expiration_is_typed_unknown() -> None:
    result = _select_atm_strikes(
        cast(OptionChain, _PutOnlyChain()),
        date(2026, 8, 28),
        Decimal("190"),
    )

    assert isinstance(result, UnknownReason)
    assert result.code == "no_call_contracts_at_selected_expiration"
