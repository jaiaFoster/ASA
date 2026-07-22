from __future__ import annotations

from decimal import Decimal

import pytest

from analytics.atm_selection import select_atm_strike


class TestSelectAtmStrike:
    def test_selects_the_closest_strike(self) -> None:
        strikes = (Decimal("195"), Decimal("200"), Decimal("205"), Decimal("210"), Decimal("215"))
        assert select_atm_strike(strikes, Decimal("207")) == Decimal("205")

    def test_exact_match_wins(self) -> None:
        strikes = (Decimal("200"), Decimal("210"), Decimal("220"))
        assert select_atm_strike(strikes, Decimal("210")) == Decimal("210")

    def test_ties_break_toward_the_lower_strike(self) -> None:
        strikes = (Decimal("205"), Decimal("215"))
        assert select_atm_strike(strikes, Decimal("210")) == Decimal("205")

    def test_empty_strikes_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            select_atm_strike((), Decimal("210"))

    def test_non_positive_spot_price_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            select_atm_strike((Decimal("210"),), Decimal("0"))
