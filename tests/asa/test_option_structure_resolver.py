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
from strategy_runtime.executable_structures import ExecutableStructureStatus
from strategy_runtime.option_structure_resolver import (
    OptionLegIntent,
    OptionStructureIntent,
    resolve_option_structure,
)

NOW = datetime(2026, 9, 1, 15, tzinfo=UTC)
FRONT = date(2026, 9, 18)
BACK = date(2026, 10, 16)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "chain-observation", 1),)
INSTRUMENT = Instrument(
    CanonicalInstrumentIdentity("symbol", "AAPL"), InstrumentKind.EQUITY, "AAPL", "USD"
)
SECURITY = Security(INSTRUMENT, "AAPL", SecurityAssetType.EQUITY, "NASDAQ")


def _contract(expiration: date, strike: str, delta: str | None = "0.50") -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("occ", f"AAPL-{expiration}-{strike}-C"),
        SECURITY,
        expiration,
        Decimal(strike),
        OptionType.CALL,
        Decimal("2.00"),
        Decimal("2.20"),
        Decimal("2.10"),
        10,
        100,
        None if delta is None else Decimal(delta),
        None,
        None,
        None,
        None,
        Decimal("0.30"),
        NOW,
        EVIDENCE,
    )


def _chain(*contracts: OptionContract) -> OptionChain:
    return OptionChain("AAPL-chain", SECURITY, NOW, contracts, EVIDENCE)


def _calendar(front_strike: str, back_strike: str) -> OptionStructureIntent:
    return OptionStructureIntent(
        "AAPL",
        StructureKind.CALENDAR,
        (
            OptionLegIntent(
                "front",
                OptionType.CALL,
                FRONT,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_strike=Decimal(front_strike),
            ),
            OptionLegIntent(
                "back",
                OptionType.CALL,
                BACK,
                OptionLegPosition.LONG,
                Decimal(1),
                selected_strike=Decimal(back_strike),
            ),
        ),
    )


def _resolve(intent: OptionStructureIntent, chain: OptionChain):  # type: ignore[no-untyped-def]
    return resolve_option_structure(
        intent=intent,
        chain=chain,
        originating_result_identity="result-1",
        evidence_snapshot_identity="snapshot-1",
        assessed_at=NOW,
    )


def test_same_strike_calendar_resolves_exact_contracts_and_midpoint_entry() -> None:
    result = _resolve(
        _calendar("200", "200"),
        _chain(_contract(FRONT, "200"), _contract(BACK, "200")),
    )

    assert result.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    assert result.available_structure_kind is StructureKind.CALENDAR
    assert tuple(item.leg.contract.strike for item in result.exact_legs) == (
        Decimal("200"),
        Decimal("200"),
    )
    assert result.modeled_entry_economics is not None
    assert result.modeled_entry_economics.modeled_net_debit_or_credit == Decimal("0.00")


def test_diagonal_only_counterexample_is_not_substituted_for_calendar() -> None:
    result = _resolve(
        _calendar("200", "205"),
        _chain(_contract(FRONT, "200"), _contract(BACK, "205")),
    )

    assert result.status is ExecutableStructureStatus.DIFFERENT_STRUCTURE_AVAILABLE
    assert result.available_structure_kind is StructureKind.CUSTOM
    assert result.reason_code == "resolved_legs_form_different_structure"


def test_no_compatible_contract_is_typed_not_constructible() -> None:
    result = _resolve(_calendar("200", "200"), _chain(_contract(FRONT, "205")))

    assert result.status is ExecutableStructureStatus.NOT_CONSTRUCTIBLE
    assert result.reason_code == "no_compatible_contract"
    assert result.exact_legs == ()


def test_delta_selection_is_deterministic_and_records_target_vs_actual() -> None:
    intent = OptionStructureIntent(
        "AAPL",
        StructureKind.VERTICAL,
        (
            OptionLegIntent(
                "long",
                OptionType.CALL,
                FRONT,
                OptionLegPosition.LONG,
                Decimal(1),
                target_delta=Decimal("0.50"),
            ),
            OptionLegIntent(
                "short",
                OptionType.CALL,
                FRONT,
                OptionLegPosition.SHORT,
                Decimal(1),
                target_delta=Decimal("0.25"),
            ),
        ),
    )
    chain = _chain(
        _contract(FRONT, "200", "0.48"),
        _contract(FRONT, "205", "0.27"),
        _contract(FRONT, "210", "0.20"),
    )

    result = _resolve(intent, chain)

    assert result.status is ExecutableStructureStatus.CONSTRUCTIBLE_AS_INTENDED
    assert tuple(item.leg.contract.strike for item in result.exact_legs) == (
        Decimal("200"),
        Decimal("205"),
    )
    assert tuple(item.actual_delta for item in result.selection_diagnostics) == (
        Decimal("0.48"),
        Decimal("0.27"),
    )


def test_missing_delta_is_typed_unknown() -> None:
    intent = OptionStructureIntent(
        "AAPL",
        StructureKind.VERTICAL,
        (
            OptionLegIntent(
                "long",
                OptionType.CALL,
                FRONT,
                OptionLegPosition.LONG,
                Decimal(1),
                target_delta=Decimal("0.50"),
            ),
            OptionLegIntent(
                "short",
                OptionType.CALL,
                FRONT,
                OptionLegPosition.SHORT,
                Decimal(1),
                selected_strike=Decimal("205"),
            ),
        ),
    )

    result = _resolve(
        intent,
        _chain(_contract(FRONT, "200", None), _contract(FRONT, "205", None)),
    )

    assert result.status is ExecutableStructureStatus.UNKNOWN
    assert result.reason_code == "missing_actual_delta"
