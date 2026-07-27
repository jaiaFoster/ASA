"""SPRINT-011-CLOSEOUT/CLOSE-002: select_nearest_delta_contract() -- a
screening-layer-owned delta lookup used only to measure a real skew
signal for scoring, decoupled from strategies/stonk_components.py's own
private _nearest_delta (see screening/live_context.py's own module
docstring for why screening/ cannot reach into strategies/'s internals).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionType,
    Security,
    SecurityAssetType,
)
from screening.live_context import NoContractNearDeltaError, select_nearest_delta_contract

NOW = datetime(2026, 7, 22, 16, 0, tzinfo=UTC)
EXPIRATION = NOW.date()
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "test"),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"), InstrumentKind.EQUITY, "AAPL", "USD"
)
SECURITY = Security(INSTRUMENT, "AAPL", SecurityAssetType.EQUITY, "XNAS")


def _contract(
    strike: Decimal, delta: Decimal, option_type: OptionType = OptionType.CALL
) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("fixture-option", f"AAPL-{strike}-{option_type.value}"),
        SECURITY,
        EXPIRATION,
        strike,
        option_type,
        Decimal("4.90"),
        Decimal("5.10"),
        Decimal("5.00"),
        1000,
        5000,
        delta,
        Decimal("0.03"),
        Decimal("-0.10"),
        Decimal("0.20"),
        Decimal("0.01"),
        Decimal("0.30"),
        NOW,
        EVIDENCE,
    )


def _chain(contracts: tuple[OptionContract, ...]) -> OptionChain:
    return OptionChain("fixture:delta-selection", SECURITY, NOW, contracts, EVIDENCE)


class TestSelectNearestDeltaContract:
    def test_selects_the_contract_closest_to_the_target_delta(self) -> None:
        chain = _chain(
            (
                _contract(Decimal("95"), Decimal("0.60")),
                _contract(Decimal("100"), Decimal("0.50")),
                _contract(Decimal("105"), Decimal("0.25")),
                _contract(Decimal("110"), Decimal("0.10")),
            )
        )
        selected = select_nearest_delta_contract(
            chain, EXPIRATION, OptionType.CALL, Decimal("0.25")
        )
        assert selected.strike == Decimal("105")

    def test_excludes_the_given_strike(self) -> None:
        chain = _chain(
            (
                _contract(Decimal("100"), Decimal("0.26")),
                _contract(Decimal("105"), Decimal("0.20")),
            )
        )
        # Without exclusion the 100-strike (delta 0.26) is nearer to 0.25;
        # excluding it must fall through to the next-nearest candidate.
        selected = select_nearest_delta_contract(
            chain, EXPIRATION, OptionType.CALL, Decimal("0.25"), exclude_strike=Decimal("100")
        )
        assert selected.strike == Decimal("105")

    def test_ignores_contracts_with_no_delta(self) -> None:
        chain = _chain((_contract(Decimal("100"), Decimal("0.50")),))
        no_delta = OptionContract(
            CanonicalInstrumentIdentity("fixture-option", "AAPL-105-call"),
            SECURITY,
            EXPIRATION,
            Decimal("105"),
            OptionType.CALL,
            Decimal("4.90"),
            Decimal("5.10"),
            Decimal("5.00"),
            1000,
            5000,
            None,
            Decimal("0.03"),
            Decimal("-0.10"),
            Decimal("0.20"),
            Decimal("0.01"),
            Decimal("0.30"),
            NOW,
            EVIDENCE,
        )
        chain_with_gap = OptionChain(
            "fixture:delta-selection", SECURITY, NOW, chain.contracts + (no_delta,), EVIDENCE
        )
        selected = select_nearest_delta_contract(
            chain_with_gap, EXPIRATION, OptionType.CALL, Decimal("0.25")
        )
        assert selected.strike == Decimal("100")  # the only candidate with a populated delta

    def test_raises_when_no_candidate_has_a_delta(self) -> None:
        no_delta = OptionContract(
            CanonicalInstrumentIdentity("fixture-option", "AAPL-100-call"),
            SECURITY,
            EXPIRATION,
            Decimal("100"),
            OptionType.CALL,
            Decimal("4.90"),
            Decimal("5.10"),
            Decimal("5.00"),
            1000,
            5000,
            None,
            Decimal("0.03"),
            Decimal("-0.10"),
            Decimal("0.20"),
            Decimal("0.01"),
            Decimal("0.30"),
            NOW,
            EVIDENCE,
        )
        with pytest.raises(NoContractNearDeltaError):
            select_nearest_delta_contract(
                _chain((no_delta,)), EXPIRATION, OptionType.CALL, Decimal("0.25")
            )
