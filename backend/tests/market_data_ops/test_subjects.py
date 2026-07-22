from __future__ import annotations

from datetime import UTC, datetime

from asa.market_data_ops.subjects import build_validation_subject
from domain import MarketCapability

AS_OF = datetime(2026, 7, 22, 6, 0, tzinfo=UTC)


def test_option_chain_subject_carries_a_future_expiration_projection() -> None:
    """TradierProvider._endpoint() requires an "expiration" projection for
    OPTION_CHAIN_V1 whenever required_fields is ("contracts",) (the fixed
    validation subject's required_fields). Without one, subject.projection_for()
    raised DomainInvariantError uncaught before any transport call was made --
    this reproduces the live crash discovered during POST-005B-LIVE-VALIDATION
    Phase 4 and confirms the fix.
    """
    subject = build_validation_subject("tradier", MarketCapability.OPTION_CHAIN_V1, as_of=AS_OF)
    projection = subject.projection_for("tradier", "expiration", AS_OF)
    expiration = datetime.fromisoformat(projection.address_value).date()
    assert expiration > AS_OF.date()
    assert expiration.weekday() == 4  # Friday
    assert 15 <= expiration.day <= 21  # third Friday of the month


def test_non_option_capabilities_are_unaffected() -> None:
    for capability in (
        MarketCapability.REAL_TIME_QUOTE_V1,
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.EARNINGS_CALENDAR_V1,
    ):
        subject = build_validation_subject("tradier", capability, as_of=AS_OF)
        assert len(subject.request_context.provider_address_projections) == 1
