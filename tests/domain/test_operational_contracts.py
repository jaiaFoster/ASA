"""ASA-ARCH-001 operational contract regression coverage."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    DomainInvariantError,
    EvidenceKind,
    EvidenceReference,
    Holding,
    Instrument,
    InstrumentKind,
    MonetaryAmount,
    PortfolioDecisionRequest,
    PortfolioSnapshot,
    PositionDirection,
    ProposedPosition,
    SectorClassification,
)

NOW = datetime(2026, 7, 22, tzinfo=timezone.utc)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "obs-portfolio-1"),)
USD = "USD"


def _instrument() -> Instrument:
    return Instrument(
        identity=CanonicalInstrumentIdentity("figi", "BBG000B9XRY4"),
        kind=InstrumentKind.EQUITY,
        display_symbol="AAPL",
        currency=USD,
        sector=SectorClassification("GICS", "2023", "45"),
    )


def _holding(**overrides: object) -> Holding:
    values: dict[str, object] = {
        "holding_id": "holding-1",
        "account_id": "account-1",
        "instrument": _instrument(),
        "direction": PositionDirection.LONG,
        "quantity": Decimal("10"),
        "market_value": MonetaryAmount(Decimal("2100"), USD),
        "gross_exposure": MonetaryAmount(Decimal("2100"), USD),
        "valued_at": NOW,
        "valuation_evidence": EVIDENCE,
    }
    values.update(overrides)
    return Holding(**values)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> PortfolioSnapshot:
    values: dict[str, object] = {
        "portfolio_snapshot_id": "snapshot-1",
        "portfolio_id": "portfolio-1",
        "base_currency": USD,
        "holdings": (_holding(),),
        "cash_balance": MonetaryAmount(Decimal("5000"), USD),
        "buying_power": MonetaryAmount(Decimal("8000"), USD),
        "net_liquidation_value": MonetaryAmount(Decimal("7100"), USD),
        "gross_exposure": MonetaryAmount(Decimal("2100"), USD),
        "observed_at": NOW,
        "evidence": EVIDENCE,
    }
    values.update(overrides)
    return PortfolioSnapshot(**values)  # type: ignore[arg-type]


def _proposal(**overrides: object) -> ProposedPosition:
    values: dict[str, object] = {
        "proposed_position_id": "proposal-1",
        "opportunity_id": "opportunity-1",
        "ranking_result_id": "ranking-result-1",
        "ranking_id": "ranked-opportunity-1",
        "portfolio_id": "portfolio-1",
        "account_id": "account-1",
        "instrument": _instrument(),
        "direction": PositionDirection.LONG,
        "quantity": Decimal("2"),
        "estimated_unit_price": MonetaryAmount(Decimal("210"), USD),
        "gross_exposure": MonetaryAmount(Decimal("420"), USD),
        "evidence": EVIDENCE,
    }
    values.update(overrides)
    return ProposedPosition(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        _instrument(),
        _holding(),
        _snapshot(),
        _proposal(),
        PortfolioDecisionRequest(
            "request-1", "ranking-result-1", _snapshot(), (_proposal(),)
        ),
    ],
)
def test_operational_contracts_are_deeply_immutable(value: object) -> None:
    assert dataclasses.is_dataclass(value)
    assert value.__dataclass_params__.frozen  # type: ignore[attr-defined]
    first_field = dataclasses.fields(value)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value, first_field, "changed")
    assert all(
        not isinstance(getattr(value, field.name), (list, dict, set))
        for field in dataclasses.fields(value)
    )


def test_instrument_identity_is_opaque_and_not_derived_from_display_symbol() -> None:
    first = _instrument()
    renamed = dataclasses.replace(first, display_symbol="APPLE")
    assert renamed.identity == first.identity


def test_option_requires_explicit_underlying_identity() -> None:
    with pytest.raises(DomainInvariantError, match="underlying_identity is required"):
        Instrument(
            identity=CanonicalInstrumentIdentity("occ", "AAPL270115C00200000"),
            kind=InstrumentKind.OPTION,
            display_symbol="AAPL 2027-01-15 200C",
            currency=USD,
        )


def test_snapshot_keeps_cash_and_buying_power_distinct() -> None:
    snapshot = _snapshot(
        cash_balance=MonetaryAmount(Decimal("-100"), USD),
        buying_power=MonetaryAmount(Decimal("500"), USD),
    )
    assert snapshot.cash_balance.amount == Decimal("-100")
    assert snapshot.buying_power.amount == Decimal("500")


def test_account_only_snapshot_is_supported() -> None:
    snapshot = _snapshot(
        holdings=(),
        gross_exposure=MonetaryAmount(Decimal("0"), USD),
    )
    assert snapshot.holdings == ()


def test_snapshot_rejects_negative_buying_power() -> None:
    with pytest.raises(DomainInvariantError, match="buying_power.amount cannot be negative"):
        _snapshot(buying_power=MonetaryAmount(Decimal("-0.01"), USD))


def test_snapshot_rejects_mixed_valuation_currencies() -> None:
    with pytest.raises(DomainInvariantError, match="must use base_currency"):
        _snapshot(cash_balance=MonetaryAmount(Decimal("5000"), "EUR"))


def test_holding_requires_explicit_valuation_evidence() -> None:
    with pytest.raises(DomainInvariantError, match="valuation_evidence cannot be empty"):
        _holding(valuation_evidence=())


def test_decision_request_preserves_rank_order_and_requires_matching_ids() -> None:
    first = _proposal()
    second = _proposal(
        proposed_position_id="proposal-2",
        opportunity_id="opportunity-2",
    )
    request = PortfolioDecisionRequest(
        "request-1", "ranking-result-1", _snapshot(), (first, second)
    )
    assert request.proposed_positions == (first, second)

    with pytest.raises(DomainInvariantError, match="reference ranking_result_id"):
        PortfolioDecisionRequest(
            "request-2",
            "other-ranking",
            _snapshot(),
            (first,),
        )


def test_contract_fields_contain_no_broker_or_repository_models() -> None:
    field_names = {
        field.name
        for cls in (Instrument, Holding, PortfolioSnapshot, ProposedPosition)
        for field in dataclasses.fields(cls)
    }
    assert not any("broker" in name or "repository" in name for name in field_names)
