"""ASA-ARCH-005 immutable financial-contract regression coverage."""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain import (
    AnnouncementTime,
    CanonicalInstrumentIdentity,
    DomainInvariantError,
    EarningsCalendar,
    EarningsEvent,
    EarningsHistoryEntry,
    EvidenceKind,
    EvidenceReference,
    ExpirationCollection,
    ExpirationCycle,
    FinancialContractSerializationError,
    Instrument,
    InstrumentKind,
    OptionChain,
    OptionCollection,
    OptionContract,
    OptionLeg,
    OptionLegPosition,
    OptionStructure,
    OptionStructureType,
    OptionType,
    Security,
    SecurityAssetType,
    SecurityCollection,
    VolatilityEvidence,
    deserialize_financial_contract,
    serialize_financial_contract,
)

NOW = datetime(2026, 7, 21, 16, 0, tzinfo=timezone.utc)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "observation-1"),)


def security(symbol: str = "AAPL") -> Security:
    return Security(
        Instrument(
            CanonicalInstrumentIdentity("figi", f"figi-{symbol}"),
            InstrumentKind.EQUITY,
            symbol,
            "USD",
        ),
        symbol,
        SecurityAssetType.EQUITY,
        "XNAS",
    )


def option(
    *,
    expiration: date = date(2026, 8, 21),
    strike: Decimal = Decimal("200"),
    option_type: OptionType = OptionType.CALL,
    observed_at: datetime = NOW,
    underlying: Security | None = None,
    suffix: str = "1",
) -> OptionContract:
    return OptionContract(
        CanonicalInstrumentIdentity("asa-option-v1", f"option-{suffix}"),
        underlying or security(),
        expiration,
        strike,
        option_type,
        Decimal("4.10"),
        Decimal("4.30"),
        Decimal("4.20"),
        100,
        500,
        Decimal("0.50"),
        Decimal("0.03"),
        Decimal("-0.08"),
        Decimal("0.12"),
        Decimal("0.01"),
        Decimal("0.35"),
        observed_at,
        EVIDENCE,
    )


def all_contracts() -> tuple[object, ...]:
    underlying = security()
    call = option(underlying=underlying)
    put = option(
        underlying=underlying,
        option_type=OptionType.PUT,
        suffix="2",
    )
    cycle = ExpirationCycle(date(2026, 8, 21), 31, True, False, date(2026, 7, 21), EVIDENCE)
    history = EarningsHistoryEntry(
        date(2026, 4, 20), AnnouncementTime.AFTER_CLOSE, Decimal("0.04"), EVIDENCE
    )
    event = EarningsEvent(
        "earnings-1",
        underlying,
        date(2026, 7, 30),
        AnnouncementTime.AFTER_CLOSE,
        Decimal("0.05"),
        True,
        (history,),
        NOW,
        EVIDENCE,
    )
    leg = OptionLeg(call, OptionLegPosition.LONG, Decimal("1"), "long_call")
    return (
        underlying,
        SecurityCollection((underlying,)),
        call,
        OptionCollection((put, call)),
        OptionChain("chain-1", underlying, NOW, (put, call), EVIDENCE),
        cycle,
        ExpirationCollection(date(2026, 7, 21), (cycle,)),
        history,
        event,
        EarningsCalendar(date(2026, 7, 1), date(2026, 7, 31), NOW, (event,), EVIDENCE),
        VolatilityEvidence(
            underlying,
            Decimal("0.35"),
            Decimal("0.25"),
            Decimal("0.60"),
            Decimal("0.70"),
            timedelta(days=252),
            NOW,
            EVIDENCE,
        ),
        leg,
        OptionStructure(
            "structure-1",
            OptionStructureType.SINGLE_LEG,
            underlying,
            (leg,),
            NOW,
            EVIDENCE,
        ),
    )


@pytest.mark.parametrize("value", all_contracts())
def test_every_contract_is_immutable_and_round_trips_canonically(value: object) -> None:
    assert dataclasses.is_dataclass(value)
    assert value.__dataclass_params__.frozen  # type: ignore[attr-defined]
    payload = serialize_financial_contract(value)  # type: ignore[arg-type]
    assert deserialize_financial_contract(payload) == value
    assert (
        json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":")).encode() == payload
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value, dataclasses.fields(value)[0].name, "changed")


def test_structural_option_identity_excludes_observation_evidence() -> None:
    first = option()
    later = dataclasses.replace(
        first,
        bid=Decimal("5"),
        ask=Decimal("5.20"),
        mark=Decimal("5.10"),
        observed_at=NOW + timedelta(hours=1),
    )
    assert later.identity == first.identity
    assert later.observation_identity != first.observation_identity


def test_collection_input_order_does_not_change_identity_or_serialization() -> None:
    first = option(strike=Decimal("195"), suffix="1")
    second = option(strike=Decimal("205"), suffix="2")
    left = OptionChain("chain-1", security(), NOW, (first, second), EVIDENCE)
    right = OptionChain("chain-1", security(), NOW, (second, first), EVIDENCE)
    assert left == right
    assert left.identity == right.identity
    assert serialize_financial_contract(left) == serialize_financial_contract(right)


def test_option_chain_lookup_is_pure_and_exact() -> None:
    call = option(suffix="call")
    put = option(option_type=OptionType.PUT, suffix="put")
    chain = OptionChain("chain-1", security(), NOW, (put, call), EVIDENCE)
    assert chain.find(option_type=OptionType.CALL) == (call,)
    assert chain.contracts == tuple(sorted((call, put), key=lambda item: item.option_type.value))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"strike": Decimal("0")}, "greater than zero"),
        ({"bid": Decimal("5"), "ask": Decimal("4")}, "crossed"),
        ({"expiration": date(2026, 7, 20)}, "precede observed_at"),
        ({"volume": -1}, "non-negative integer"),
        ({"implied_volatility": Decimal("NaN")}, "finite"),
    ],
)
def test_invalid_option_evidence_fails_closed(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(DomainInvariantError, match=message):
        dataclasses.replace(option(), **overrides)


def test_expiration_cycle_uses_explicit_semantic_date() -> None:
    with pytest.raises(DomainInvariantError, match="date delta"):
        ExpirationCycle(date(2026, 8, 21), 30, True, False, date(2026, 7, 21), EVIDENCE)
    first = ExpirationCycle(date(2026, 8, 21), 31, True, False, date(2026, 7, 21), EVIDENCE)
    second = ExpirationCycle(date(2026, 8, 21), 30, True, False, date(2026, 7, 22), EVIDENCE)
    assert first.identity != second.identity


def test_earnings_history_is_canonical_and_precedes_event() -> None:
    newer = EarningsHistoryEntry(date(2026, 4, 20), AnnouncementTime.AFTER_CLOSE, None, EVIDENCE)
    older = EarningsHistoryEntry(date(2026, 1, 20), AnnouncementTime.AFTER_CLOSE, None, EVIDENCE)
    event = EarningsEvent(
        "event-1",
        security(),
        date(2026, 7, 30),
        AnnouncementTime.UNKNOWN,
        None,
        False,
        (older, newer),
        NOW,
        EVIDENCE,
    )
    assert event.historical_sequence == (newer, older)
    with pytest.raises(DomainInvariantError, match="precede"):
        dataclasses.replace(
            event,
            historical_sequence=(dataclasses.replace(newer, earnings_date=event.earnings_date),),
        )


def test_volatility_requires_explicit_value_and_positive_lookback() -> None:
    with pytest.raises(DomainInvariantError, match="at least one"):
        VolatilityEvidence(security(), None, None, None, None, timedelta(days=1), NOW, EVIDENCE)
    with pytest.raises(DomainInvariantError, match="positive duration"):
        VolatilityEvidence(
            security(), Decimal("0.2"), None, None, None, timedelta(0), NOW, EVIDENCE
        )


def test_option_structure_enforces_closed_shapes_without_portfolio_policy() -> None:
    lower = OptionLeg(
        option(strike=Decimal("195"), suffix="lower"), OptionLegPosition.LONG, Decimal("1"), "long"
    )
    upper = OptionLeg(
        option(strike=Decimal("205"), suffix="upper"),
        OptionLegPosition.SHORT,
        Decimal("1"),
        "short",
    )
    vertical = OptionStructure(
        "vertical-1", OptionStructureType.VERTICAL, security(), (upper, lower), NOW, EVIDENCE
    )
    assert vertical.legs == (lower, upper)
    with pytest.raises(DomainInvariantError, match="vertical shape"):
        OptionStructure(
            "invalid",
            OptionStructureType.VERTICAL,
            security(),
            (
                lower,
                dataclasses.replace(
                    upper,
                    contract=dataclasses.replace(upper.contract, expiration=date(2026, 9, 18)),
                ),
            ),
            NOW,
            EVIDENCE,
        )


def test_deserializer_rejects_unknown_version_and_noncanonical_json() -> None:
    payload = serialize_financial_contract(security())
    root = json.loads(payload)
    root["contract_version"] = "v2"
    with pytest.raises(FinancialContractSerializationError, match="unsupported"):
        deserialize_financial_contract(
            json.dumps(root, sort_keys=True, separators=(",", ":")).encode()
        )
    with pytest.raises(FinancialContractSerializationError, match="not canonical"):
        deserialize_financial_contract(json.dumps(json.loads(payload), indent=2).encode())
