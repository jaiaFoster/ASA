"""Fixtures for the ARCH-006 analytical execution path."""

from datetime import datetime, timezone
from decimal import Decimal

from domain.operational import (
    Instrument,
    InstrumentValuation,
    MonetaryAmount,
    Portfolio,
    PortfolioEvaluationRequest,
    PortfolioSnapshot,
    RiskPolicy,
    RiskPolicyScope,
    RiskPolicyType,
)
from domain.references import EvidenceKind, EvidenceReference
from position_proposals.engine import propose_positions
from ranking.engine import rank_opportunities
from tests.instrument_helpers import TEST_INSTRUMENT
from tests.ranking.helpers import evaluation

NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "portfolio-observation"),)


def policy(policy_type: RiskPolicyType, parameters: tuple[tuple[str, Decimal | bool], ...]) -> RiskPolicy:
    return RiskPolicy(
        f"platform-{policy_type.value}", policy_type, RiskPolicyScope.PLATFORM, "v1",
        parameters, None, ("platform v1 policy",), EVIDENCE,
    )


def policies() -> tuple[RiskPolicy, ...]:
    return (
        policy(RiskPolicyType.BUYING_POWER, (("minimum_remaining_amount", Decimal("0")),)),
        policy(RiskPolicyType.CASH_RESERVE, (("minimum_cash_ratio", Decimal("0")),)),
        policy(RiskPolicyType.DUPLICATE_EXPOSURE, (("allow_increase_existing", True),)),
        policy(RiskPolicyType.MAXIMUM_LOSS, (("maximum_amount", Decimal("1000000")),)),
        policy(RiskPolicyType.MAX_POSITION_ALLOCATION, (("maximum_ratio", Decimal("1")),)),
        policy(RiskPolicyType.MAX_SECTOR_EXPOSURE, (("maximum_ratio", Decimal("1")),)),
        policy(RiskPolicyType.MAX_SINGLE_ASSET_EXPOSURE, (("maximum_ratio", Decimal("1")),)),
    )


def valuation(instrument: Instrument = TEST_INSTRUMENT) -> InstrumentValuation:
    return InstrumentValuation(
        "valuation-aapl", instrument, "account-1", MonetaryAmount(Decimal("100"), "USD"),
        Decimal("1"), MonetaryAmount(Decimal("100"), "USD"), Decimal("1"), NOW, EVIDENCE,
    )


def snapshot(*, cash: Decimal = Decimal("100000"), buying_power: Decimal = Decimal("50000")) -> PortfolioSnapshot:
    portfolio = Portfolio(
        "portfolio-1", "portfolio-state-1", 1, "account-1", "USD", Decimal("0.01"), (),
        MonetaryAmount(cash, "USD"), MonetaryAmount(buying_power, "USD"),
        MonetaryAmount(cash, "USD"), MonetaryAmount(Decimal("0"), "USD"),
        MonetaryAmount(Decimal("0"), "USD"), MonetaryAmount(Decimal("0"), "USD"),
        policies(), EVIDENCE,
    )
    return PortfolioSnapshot("snapshot-1", portfolio, (valuation(),), NOW, EVIDENCE)


def proposal():  # type: ignore[no-untyped-def]
    ranking = rank_opportunities((evaluation("candidate", expected_return="0.20"),))
    return propose_positions(ranking)[0]


def request(portfolio_snapshot: PortfolioSnapshot | None = None) -> PortfolioEvaluationRequest:
    item = proposal()
    return PortfolioEvaluationRequest(
        "evaluation-request-1", item.ranking_result_id, portfolio_snapshot or snapshot(), (item,)
    )
