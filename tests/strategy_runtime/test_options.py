"""SPRINT-009/EPIC-4: universal options framework.

Builds real domain.OptionContract/OptionLeg/OptionStructure instances
(domain/financial.py's own already-validated types) rather than fakes --
proving strategy_runtime.options works against the real, already-shipped
option package representation, not a stand-in.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionContract,
    OptionLeg,
    OptionLegPosition,
    OptionStructure,
    OptionStructureType,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategy_runtime.options import (
    ExpirationCandidate,
    LiquidityPolicy,
    compute_structure_debit,
    is_liquid,
    liquidity_blockers,
    select_earnings_relative_expiration_pair,
    select_expiration_pair,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=UTC)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "observation-1"),)


def _security(symbol: str = "AAPL") -> Security:
    instrument = Instrument(
        CanonicalInstrumentIdentity("figi", f"figi-{symbol}"), InstrumentKind.EQUITY, symbol, "USD"
    )
    return Security(instrument, symbol, SecurityAssetType.EQUITY, "XNAS")


def _contract(
    *,
    expiration: date = date(2026, 8, 21),
    strike: Decimal = Decimal("200"),
    option_type: OptionType = OptionType.CALL,
    bid: Decimal | None = Decimal("4.10"),
    ask: Decimal | None = Decimal("4.30"),
    mark: Decimal | None = Decimal("4.20"),
    volume: int | None = 100,
    open_interest: int | None = 500,
    suffix: str = "1",
) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("asa-option-v1", f"option-{suffix}"),
        _security(),
        expiration,
        strike,
        option_type,
        bid,
        ask,
        mark,
        volume,
        open_interest,
        Decimal("0.50"),
        Decimal("0.03"),
        Decimal("-0.08"),
        Decimal("0.12"),
        Decimal("0.01"),
        Decimal("0.35"),
        NOW,
        EVIDENCE,
    )


def _leg(contract: OptionContract, position: OptionLegPosition, role: str) -> OptionLeg:
    return OptionLeg(contract, position, Decimal(1), role)


_POLICY = LiquidityPolicy(
    maximum_spread_ratio=Decimal("0.10"), minimum_open_interest=50, minimum_volume=10
)


class TestLiquidityPolicy:
    def test_negative_threshold_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            LiquidityPolicy(Decimal("-0.1"), 0, 0)


class TestIsLiquid:
    def test_within_thresholds_is_liquid(self) -> None:
        assert is_liquid(_contract(), _POLICY)

    def test_missing_bid_is_not_liquid(self) -> None:
        assert not is_liquid(_contract(bid=None), _POLICY)

    def test_zero_mark_is_not_liquid(self) -> None:
        assert not is_liquid(_contract(mark=Decimal("0")), _POLICY)

    def test_wide_spread_is_not_liquid(self) -> None:
        # (ask - bid) / mark = (5.00 - 3.00) / 4.00 = 0.50 > 0.10
        assert not is_liquid(_contract(bid=Decimal("3.00"), ask=Decimal("5.00")), _POLICY)

    def test_low_open_interest_is_not_liquid(self) -> None:
        assert not is_liquid(_contract(open_interest=1), _POLICY)

    def test_low_volume_is_not_liquid(self) -> None:
        assert not is_liquid(_contract(volume=1), _POLICY)


class TestLiquidityBlockers:
    def test_all_legs_liquid_returns_no_blockers(self) -> None:
        long_leg = _leg(
            _contract(strike=Decimal("200"), suffix="long"), OptionLegPosition.LONG, "long"
        )
        short_leg = _leg(
            _contract(strike=Decimal("210"), suffix="short"), OptionLegPosition.SHORT, "short"
        )
        structure = OptionStructure(
            "structure-1",
            OptionStructureType.VERTICAL,
            _security(),
            (long_leg, short_leg),
            NOW,
            EVIDENCE,
        )
        assert liquidity_blockers(structure, _POLICY) == ()

    def test_one_illiquid_leg_produces_one_blocker(self) -> None:
        long_leg = _leg(
            _contract(strike=Decimal("200"), suffix="long"), OptionLegPosition.LONG, "long"
        )
        illiquid_short = _leg(
            _contract(strike=Decimal("210"), suffix="short", volume=1),
            OptionLegPosition.SHORT,
            "short",
        )
        structure = OptionStructure(
            "structure-2",
            OptionStructureType.VERTICAL,
            _security(),
            (long_leg, illiquid_short),
            NOW,
            EVIDENCE,
        )
        blockers = liquidity_blockers(structure, _POLICY)
        assert len(blockers) == 1
        assert "short" in blockers[0]


class TestComputeStructureDebit:
    def test_vertical_debit_from_marks_and_conservative_fills(self) -> None:
        long_leg = _leg(
            _contract(
                strike=Decimal("200"),
                suffix="long",
                bid=Decimal("4.00"),
                ask=Decimal("4.20"),
                mark=Decimal("4.10"),
            ),
            OptionLegPosition.LONG,
            "long",
        )
        short_leg = _leg(
            _contract(
                strike=Decimal("210"),
                suffix="short",
                bid=Decimal("1.80"),
                ask=Decimal("2.00"),
                mark=Decimal("1.90"),
            ),
            OptionLegPosition.SHORT,
            "short",
        )
        structure = OptionStructure(
            "structure-3",
            OptionStructureType.VERTICAL,
            _security(),
            (long_leg, short_leg),
            NOW,
            EVIDENCE,
        )

        debit = compute_structure_debit(structure)

        # mid: +4.10 (long mark) - 1.90 (short mark) = 2.20
        assert debit.mid_debit == Decimal("2.20")
        # conservative: +4.20 (long ask) - 1.80 (short bid) = 2.40
        assert debit.conservative_debit == Decimal("2.40")

    def test_missing_mark_on_any_leg_yields_none_mid_debit(self) -> None:
        long_leg = _leg(
            _contract(strike=Decimal("200"), suffix="long", mark=None),
            OptionLegPosition.LONG,
            "long",
        )
        short_leg = _leg(
            _contract(strike=Decimal("210"), suffix="short"), OptionLegPosition.SHORT, "short"
        )
        structure = OptionStructure(
            "structure-4",
            OptionStructureType.VERTICAL,
            _security(),
            (long_leg, short_leg),
            NOW,
            EVIDENCE,
        )

        debit = compute_structure_debit(structure)

        assert debit.mid_debit is None
        assert debit.conservative_debit is not None  # bid/ask were still present


class TestExpirationPairingReExport:
    def test_select_expiration_pair_is_the_analytics_module_re_export(self) -> None:
        candidates = (
            ExpirationCandidate(date(2026, 8, 21), 30),
            ExpirationCandidate(date(2026, 9, 18), 58),
        )
        selected = select_expiration_pair(
            candidates,
            front_min_dte=20,
            front_max_dte=40,
            back_min_dte=50,
            back_max_dte=70,
            minimum_gap_days=10,
            maximum_gap_days=40,
            target_front_dte=30,
            target_gap_days=28,
        )
        assert selected is not None
        front, back = selected
        assert front.expiration_date == date(2026, 8, 21)
        assert back.expiration_date == date(2026, 9, 18)

    def test_select_earnings_relative_expiration_pair_is_importable(self) -> None:
        assert callable(select_earnings_relative_expiration_pair)
