from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from analytics.derived_facts import DERIVED_FACT_REGISTRY, WINDOWED_OPTION_TRADE_VWAP
from domain import (
    CanonicalInstrumentIdentity,
    CompletenessMetadata,
    DomainInvariantError,
    EvidenceKind,
    EvidenceReference,
    FreshnessMetadata,
    FreshnessStatus,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    MarketObservation,
    OptionTrade,
    OptionTradeTape,
    ProviderAddressProjection,
    ProviderProvenance,
    deserialize_market_data,
    market_observation_identity,
    serialize_market_data,
)

NOW = datetime(2026, 9, 18, 16, 0, tzinfo=UTC)
CONTRACT_ID = "SPX-2026-10-16-7000-P-AM"
EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "opra-tape:request-1"),)


def _trade(source_id: str, price: str, size: str, seconds: int) -> OptionTrade:
    event_time = NOW - timedelta(seconds=seconds)
    return OptionTrade(
        source_id,
        CONTRACT_ID,
        Decimal(price),
        Decimal(size),
        event_time,
        event_time + timedelta(milliseconds=20),
        (),
    )


def _subject() -> MarketDataSubject:
    instrument = Instrument(
        CanonicalInstrumentIdentity("occ", CONTRACT_ID),
        InstrumentKind.OPTION,
        "SPX 2026-10-16 7000P",
        "USD",
        underlying_identity=CanonicalInstrumentIdentity("index_root", "SPX"),
    )
    projection = ProviderAddressProjection(
        "opra", "v1", "option_contract", CONTRACT_ID, NOW - timedelta(days=1), None, EVIDENCE
    )
    return MarketDataSubject(
        instrument,
        MarketDataSubjectType.OPTION_UNDERLYING,
        MarketCapability.OPTION_TRADE_TAPE_V1,
        MarketDataRequestContext(
            NOW - timedelta(minutes=30),
            NOW,
            ("contract_identity", "event_time", "price", "sale_condition_codes", "size"),
            (projection,),
            EVIDENCE,
        ),
    )


def test_tape_order_identity_and_serialization_are_deterministic() -> None:
    early = _trade("t-early", "10", "1", 20)
    late = _trade("t-late", "11", "2", 10)
    tape = OptionTradeTape(CONTRACT_ID, NOW, (late, early))

    assert tape.trades == (early, late)
    assert early.identity != late.identity
    assert deserialize_market_data(serialize_market_data(tape)) == tape


def test_tape_rejects_wrong_contract_duplicate_and_impossible_observation_time() -> None:
    trade = _trade("t-1", "10", "1", 20)
    with pytest.raises(DomainInvariantError, match="share contract identity"):
        OptionTradeTape(
            CONTRACT_ID,
            NOW,
            (
                trade,
                OptionTrade(
                    "t-2",
                    "other",
                    Decimal("10"),
                    Decimal("1"),
                    trade.event_time,
                    trade.observed_time,
                    (),
                ),
            ),
        )
    with pytest.raises(DomainInvariantError, match="duplicate trades"):
        OptionTradeTape(CONTRACT_ID, NOW, (trade, trade))
    with pytest.raises(DomainInvariantError, match="cannot precede"):
        OptionTrade(
            "t-3", CONTRACT_ID, Decimal("10"), Decimal("1"), NOW, NOW - timedelta(seconds=1), ()
        )


def test_tape_is_the_only_value_for_option_trade_capability() -> None:
    tape = OptionTradeTape(CONTRACT_ID, NOW, (_trade("t-1", "10", "1", 20),))
    subject = _subject()
    identity = market_observation_identity(
        "opra", MarketCapability.OPTION_TRADE_TAPE_V1, subject, NOW, tape, "v1"
    )
    observation = MarketObservation(
        identity,
        MarketCapability.OPTION_TRADE_TAPE_V1,
        subject,
        NOW,
        NOW,
        tape,
        "v1",
        ProviderProvenance("opra", "request-1", EVIDENCE),
        FreshnessMetadata(NOW, NOW, 60, 0, FreshnessStatus.FRESH),
        CompletenessMetadata(
            ("contract_identity", "event_time", "price", "sale_condition_codes", "size"),
            ("contract_identity", "event_time", "price", "sale_condition_codes", "size"),
            (),
        ),
    )

    assert deserialize_market_data(serialize_market_data(observation)) == observation
    definition = DERIVED_FACT_REGISTRY.get(WINDOWED_OPTION_TRADE_VWAP)
    assert definition.feature_version == "1.0.0"
    assert definition.required_capabilities == (MarketCapability.OPTION_TRADE_TAPE_V1,)
