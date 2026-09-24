from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionContract,
    OptionLegPosition,
    OptionType,
    Security,
    SecurityAssetType,
)
from strategy_runtime.contract import StructureKind
from strategy_runtime.option_payoff import (
    DeterministicTerminalPayoff,
    PayoffQuantityState,
    TerminalPayoffUnknown,
    default_terminal_payoff_grid,
    model_terminal_payoff,
    terminal_payoff_to_data,
)
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)

NOW = datetime(2026, 9, 23, 16, tzinfo=UTC)
EXPIRY = date(2026, 10, 16)
BACK = date(2026, 11, 20)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "chain", 1),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("symbol", "AAPL"), InstrumentKind.EQUITY, "AAPL", "USD"
)
SECURITY = Security(INSTRUMENT, "AAPL", SecurityAssetType.EQUITY, "NASDAQ")


def _contract(strike: str, expiration: date, bid: str, ask: str) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"AAPL-{expiration}-{strike}-C"),
        SECURITY,
        expiration,
        Decimal(strike),
        OptionType.CALL,
        Decimal(bid),
        Decimal(ask),
        (Decimal(bid) + Decimal(ask)) / 2,
        1,
        100,
        Decimal("0.50"),
        None,
        None,
        None,
        None,
        Decimal("0.30"),
        NOW,
        EVIDENCE,
    )


def _vertical():  # type: ignore[no-untyped-def]
    long = _contract("100", EXPIRY, "7", "9")
    short = _contract("110", EXPIRY, "3", "5")
    return resolve_option_structure(
        intent=OptionStructureIntent(
            "AAPL",
            StructureKind.VERTICAL,
            (
                OptionLegIntent(
                    "long_lower",
                    OptionType.CALL,
                    EXPIRY,
                    OptionLegPosition.LONG,
                    Decimal(1),
                    selected_contract_identity=long.identity,
                ),
                OptionLegIntent(
                    "short_upper",
                    OptionType.CALL,
                    EXPIRY,
                    OptionLegPosition.SHORT,
                    Decimal(1),
                    selected_contract_identity=short.identity,
                ),
            ),
        ),
        chain=OptionChain("chain", SECURITY, NOW, (long, short), EVIDENCE),
        originating_result_identity="result",
        evidence_snapshot_identity="snapshot",
        assessed_at=NOW,
    )


def test_vertical_terminal_payoff_has_pinned_bounded_economics() -> None:
    result = model_terminal_payoff(
        assessment=_vertical(),
        underlying_price_grid=(Decimal("90"), Decimal("104"), Decimal("120")),
    )

    assert isinstance(result, DeterministicTerminalPayoff)
    assert tuple(item.payoff for item in result.points) == (
        Decimal("-400.00"),
        Decimal("0.00"),
        Decimal("600.00"),
    )
    assert result.maximum_loss.value == Decimal("400.00")
    assert result.maximum_profit.value == Decimal("600.00")
    assert result.breakevens == (Decimal("104"),)
    assert result.maximum_loss.state is PayoffQuantityState.SUPPORTED
    assert terminal_payoff_to_data(result)["semantics"] == (
        "deterministic_terminal_payoff_from_modeled_entry"
    )


def test_default_visualization_grid_is_deterministic_and_includes_strikes() -> None:
    grid = default_terminal_payoff_grid(_vertical())

    assert grid == tuple(sorted(set(grid)))
    assert Decimal("100") in grid
    assert Decimal("110") in grid
    assert grid[0] == Decimal("80.00")
    assert grid[-1] == Decimal("132.00")


def test_calendar_requires_model_dependent_front_expiration_value() -> None:
    front = _contract("100", EXPIRY, "3", "5")
    back = _contract("100", BACK, "7", "9")
    assessment = resolve_option_structure(
        intent=OptionStructureIntent(
            "AAPL",
            StructureKind.CALENDAR,
            (
                OptionLegIntent(
                    "short_front",
                    OptionType.CALL,
                    EXPIRY,
                    OptionLegPosition.SHORT,
                    Decimal(1),
                    selected_contract_identity=front.identity,
                ),
                OptionLegIntent(
                    "long_back",
                    OptionType.CALL,
                    BACK,
                    OptionLegPosition.LONG,
                    Decimal(1),
                    selected_contract_identity=back.identity,
                ),
            ),
        ),
        chain=OptionChain("chain", SECURITY, NOW, (front, back), EVIDENCE),
        originating_result_identity="result",
        evidence_snapshot_identity="snapshot",
        assessed_at=NOW,
    )

    result = model_terminal_payoff(
        assessment=assessment,
        underlying_price_grid=(Decimal("100"),),
    )

    assert isinstance(result, TerminalPayoffUnknown)
    assert result.reason_code == "multiple_expirations_require_model_dependent_value"


def test_uncovered_short_call_reports_unbounded_loss() -> None:
    long = _contract("100", EXPIRY, "7", "9")
    short = _contract("110", EXPIRY, "3", "5")
    assessment = resolve_option_structure(
        intent=OptionStructureIntent(
            "AAPL",
            StructureKind.VERTICAL,
            (
                OptionLegIntent(
                    "long_lower",
                    OptionType.CALL,
                    EXPIRY,
                    OptionLegPosition.LONG,
                    Decimal(1),
                    selected_contract_identity=long.identity,
                ),
                OptionLegIntent(
                    "short_upper",
                    OptionType.CALL,
                    EXPIRY,
                    OptionLegPosition.SHORT,
                    Decimal(2),
                    selected_contract_identity=short.identity,
                ),
            ),
        ),
        chain=OptionChain("chain", SECURITY, NOW, (long, short), EVIDENCE),
        originating_result_identity="result",
        evidence_snapshot_identity="snapshot",
        assessed_at=NOW,
    )

    result = model_terminal_payoff(
        assessment=assessment,
        underlying_price_grid=(Decimal("90"), Decimal("120")),
    )

    assert isinstance(result, DeterministicTerminalPayoff)
    assert result.maximum_loss.state is PayoffQuantityState.UNBOUNDED
    assert result.maximum_loss.reason == "negative_upper_tail"
