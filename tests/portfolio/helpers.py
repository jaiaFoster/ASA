"""Fixtures for deterministic Portfolio Engine tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.operational import (
    CanonicalInstrumentIdentity,
    Holding,
    Instrument,
    InstrumentKind,
    MonetaryAmount,
    PortfolioDecisionRequest,
    PortfolioSnapshot,
    PositionDirection,
    SectorClassification,
)
from domain.references import EvidenceKind, EvidenceReference
from position_proposals.engine import propose_positions
from ranking.engine import rank_opportunities
from tests.ranking.helpers import evaluation

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)
USD = "USD"
PORTFOLIO_EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "portfolio-observation"),)
VALUATION_EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "holding-valuation"),)
TECHNOLOGY = SectorClassification("GICS", "2023", "45")


def instrument(
    value: str = "BBG000B9XRY4",
    symbol: str = "AAPL",
    sector: SectorClassification | None = TECHNOLOGY,
) -> Instrument:
    return Instrument(
        CanonicalInstrumentIdentity("figi", value),
        InstrumentKind.EQUITY,
        symbol,
        USD,
        sector,
    )


def holding(
    held_instrument: Instrument | None = None,
    exposure: Decimal = Decimal("1000"),
) -> Holding:
    return Holding(
        "holding-1",
        "account-1",
        held_instrument or instrument("BBG-OTHER", "MSFT"),
        PositionDirection.LONG,
        Decimal("5"),
        MonetaryAmount(exposure, USD),
        MonetaryAmount(exposure, USD),
        NOW,
        VALUATION_EVIDENCE,
    )


def snapshot(
    *,
    holdings: tuple[Holding, ...] = (),
    cash: Decimal = Decimal("50000"),
    buying_power: Decimal = Decimal("50000"),
    net_liquidation_value: Decimal = Decimal("100000"),
) -> PortfolioSnapshot:
    gross = sum((item.gross_exposure.amount for item in holdings), Decimal("0"))
    return PortfolioSnapshot(
        "snapshot-1",
        "portfolio-1",
        USD,
        holdings,
        MonetaryAmount(cash, USD),
        MonetaryAmount(buying_power, USD),
        MonetaryAmount(net_liquidation_value, USD),
        MonetaryAmount(gross, USD),
        NOW,
        PORTFOLIO_EVIDENCE,
    )


def request(portfolio_snapshot: PortfolioSnapshot | None = None) -> PortfolioDecisionRequest:
    ranking = rank_opportunities((evaluation("candidate", expected_return="0.20"),))
    proposals = propose_positions(ranking)
    return PortfolioDecisionRequest(
        "decision-request-1",
        ranking.result_id,
        portfolio_snapshot or snapshot(),
        proposals,
    )
