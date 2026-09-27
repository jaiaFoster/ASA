from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
    CorporateActionPlaceholder,
    CorporateActionStatus,
    CorporateActionType,
    DomainInvariantError,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    IndexDividendPoints,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    ProviderAddressProjection,
    ProviderProvenance,
    SecurityMasterRecord,
    SecurityType,
    deserialize_market_data,
    market_observation_identity,
    serialize_market_data,
)

NOW = datetime(2026, 9, 18, 20, tzinfo=UTC)
EFFECTIVE_DATE = date(2026, 9, 18)
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "published:request-1"),)
SPX = Instrument(
    CanonicalInstrumentIdentity("index_root", "SPX"),
    InstrumentKind.INDEX,
    "SPX",
    "USD",
)
AAPL = Instrument(
    CanonicalInstrumentIdentity("symbol", "AAPL"),
    InstrumentKind.EQUITY,
    "AAPL",
    "USD",
)


def _subject(instrument: Instrument, capability: MarketCapability) -> MarketDataSubject:
    projection = ProviderAddressProjection(
        "published",
        "v1",
        "index" if instrument.kind is InstrumentKind.INDEX else "security",
        instrument.display_symbol,
        NOW - timedelta(days=1),
        None,
        EVIDENCE,
    )
    return MarketDataSubject(
        instrument,
        MarketDataSubjectType.INSTRUMENT,
        capability,
        MarketDataRequestContext(
            NOW - timedelta(days=5),
            NOW,
            (
                ("effective_date", "points")
                if capability is MarketCapability.INDEX_DIVIDEND_POINTS_V1
                else ("effective_date", "security_type", "shares_outstanding")
            ),
            (projection,),
            EVIDENCE,
        ),
    )


def _observation(
    value: IndexDividendPoints | SecurityMasterRecord | CorporateActionPlaceholder,
    capability: MarketCapability,
) -> MarketObservation:
    instrument = SPX if capability is MarketCapability.INDEX_DIVIDEND_POINTS_V1 else AAPL
    subject = _subject(instrument, capability)
    identity = market_observation_identity(
        "published", capability, subject, NOW, value, "v1"
    )
    required = subject.request_context.required_fields
    return MarketObservation(
        identity,
        capability,
        subject,
        NOW,
        NOW,
        value,
        "v1",
        ProviderProvenance("published", "request-1", EVIDENCE),
        FreshnessMetadata(NOW, NOW, 86400, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(required, required, ()),
    )


def test_index_dividend_points_are_index_level_effective_dated_and_replayable() -> None:
    value = IndexDividendPoints(SPX, Decimal("1.25"), EFFECTIVE_DATE)
    observation = _observation(value, MarketCapability.INDEX_DIVIDEND_POINTS_V1)

    assert deserialize_market_data(serialize_market_data(observation)) == observation
    assert observation.effective_time == NOW
    assert observation.provenance.evidence == EVIDENCE


def test_constituent_corporate_action_cannot_masquerade_as_index_dividend_points() -> None:
    action = CorporateActionPlaceholder(
        AAPL,
        CorporateActionType.DIVIDEND,
        EFFECTIVE_DATE,
        CorporateActionStatus.CONFIRMED,
    )
    with pytest.raises(DomainInvariantError, match="value does not match capability"):
        _observation(action, MarketCapability.INDEX_DIVIDEND_POINTS_V1)
    with pytest.raises(DomainInvariantError, match="must be an INDEX"):
        IndexDividendPoints(AAPL, Decimal("1"), EFFECTIVE_DATE)


def test_security_master_is_point_in_time_typed_and_replayable() -> None:
    value = SecurityMasterRecord(
        AAPL,
        SecurityType.COMMON_STOCK,
        Decimal("15204000000"),
        EFFECTIVE_DATE,
    )
    observation = _observation(value, MarketCapability.SECURITY_MASTER_V1)

    assert deserialize_market_data(serialize_market_data(observation)) == observation
    assert value.security_type is SecurityType.COMMON_STOCK
    assert value.effective_date == EFFECTIVE_DATE


def test_security_master_rejects_non_equity_and_nonpositive_shares() -> None:
    with pytest.raises(DomainInvariantError, match="must be an EQUITY"):
        SecurityMasterRecord(
            SPX, SecurityType.COMMON_STOCK, Decimal("1"), EFFECTIVE_DATE
        )
    with pytest.raises(DomainInvariantError, match="must be positive"):
        SecurityMasterRecord(
            AAPL, SecurityType.COMMON_STOCK, Decimal("0"), EFFECTIVE_DATE
        )
