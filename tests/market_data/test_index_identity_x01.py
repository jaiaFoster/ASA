"""X01 (STRATEGY-PRODUCTION-001 SP-01A): INDEX identity, index-option settlement, SOQ."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from domain import (
    CanonicalInstrumentIdentity,
    EvidenceKind,
    EvidenceReference,
    IndexSettlementValue,
    Instrument,
    InstrumentKind,
    MarketCapability,
    MarketDataRequestContext,
    MarketDataSubject,
    MarketDataSubjectType,
    OptionChain,
    OptionContract,
    OptionType,
    ProviderAddressProjection,
    Quote,
    Security,
    SecurityAssetType,
    SettlementStyle,
    deserialize_financial_contract,
    serialize_financial_contract,
)
from domain.values import DomainInvariantError
from market_data import CapabilityRequest
from market_data.index_instruments import (
    canonical_instrument_kind,
    index_option_settlement_style,
)
from screening.live_context import build_capability_subject
from tests.market_data.test_tradier import (
    NOW,
    Transport,
    authorization,
    provider,
    response,
)

EVIDENCE = (EvidenceReference(EvidenceKind.OBSERVATION, "reference:SPX"),)
SPX = Instrument(CanonicalInstrumentIdentity("symbol", "SPX"), InstrumentKind.INDEX, "SPX", "USD")
SPX_SECURITY = Security(SPX, "SPX", SecurityAssetType.INDEX, "US")


def _contract(**changes: object) -> OptionContract:
    contract = OptionContract(
        CanonicalInstrumentIdentity("occ", "SPX261016P05500000"),
        SPX_SECURITY,
        date(2026, 10, 16),
        Decimal("5500"),
        OptionType.PUT,
        Decimal("40"),
        Decimal("41"),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        NOW,
        EVIDENCE,
    )
    return replace(contract, **changes) if changes else contract


def test_index_is_its_own_kind_never_equity() -> None:
    assert canonical_instrument_kind("SPX") is InstrumentKind.INDEX
    assert canonical_instrument_kind("SPY") is InstrumentKind.EQUITY
    equity = Instrument(
        CanonicalInstrumentIdentity("symbol", "SPX"), InstrumentKind.EQUITY, "SPX", "USD"
    )
    with pytest.raises(DomainInvariantError):
        Security(equity, "SPX", SecurityAssetType.INDEX, "US")
    assert (
        Security(SPX, "SPX", SecurityAssetType.INDEX, "US").identity
        != Security(equity, "SPX", SecurityAssetType.EQUITY, "US").identity
    )


def test_settlement_style_is_typed_from_root_and_identity_bearing() -> None:
    assert index_option_settlement_style("SPX") is SettlementStyle.AM
    assert index_option_settlement_style("spxw") is SettlementStyle.PM
    assert index_option_settlement_style("XSP") is None
    assert index_option_settlement_style(None) is None
    plain = _contract()
    am = _contract(root="SPX", settlement_style=SettlementStyle.AM)
    pm = _contract(root="SPXW", settlement_style=SettlementStyle.PM)
    assert len({plain.identity, am.identity, pm.identity}) == 3
    with pytest.raises(DomainInvariantError):
        _contract(settlement_style=SettlementStyle.AM)
    with pytest.raises(DomainInvariantError):
        _contract(root="spx")


def test_optional_fields_keep_existing_wire_form_and_round_trip() -> None:
    plain = _contract()
    assert b'"root"' not in serialize_financial_contract(plain)
    assert deserialize_financial_contract(serialize_financial_contract(plain)) == plain
    am = _contract(root="SPX", settlement_style=SettlementStyle.AM)
    assert deserialize_financial_contract(serialize_financial_contract(am)) == am


def test_index_settlement_value_is_canonical_index_fact() -> None:
    soq = IndexSettlementValue(
        SPX_SECURITY, date(2026, 10, 16), SettlementStyle.AM, Decimal("5501.23"), NOW, EVIDENCE
    )
    assert deserialize_financial_contract(serialize_financial_contract(soq)) == soq
    etf = Security(
        Instrument(
            CanonicalInstrumentIdentity("symbol", "SPY"), InstrumentKind.EQUITY, "SPY", "USD"
        ),
        "SPY",
        SecurityAssetType.ETF,
        "US",
    )
    with pytest.raises(DomainInvariantError):
        IndexSettlementValue(
            etf, date(2026, 10, 16), SettlementStyle.AM, Decimal("550"), NOW, EVIDENCE
        )
    assert MarketCapability.INDEX_SETTLEMENT_VALUE_V1.value == "index_settlement_value_v1"


def _spx_request(capability: MarketCapability, fields: tuple[str, ...]) -> CapabilityRequest:
    projections = [
        ProviderAddressProjection(
            "tradier", "v1", "symbol", "SPX", NOW - timedelta(days=30), None, EVIDENCE
        )
    ]
    if capability is MarketCapability.OPTION_CHAIN_V1:
        projections.append(
            ProviderAddressProjection(
                "tradier",
                "v1",
                "expiration",
                "2026-10-16",
                NOW - timedelta(days=30),
                None,
                EVIDENCE,
            )
        )
    item = MarketDataSubject(
        SPX,
        MarketDataSubjectType.OPTION_UNDERLYING
        if capability is MarketCapability.OPTION_CHAIN_V1
        else MarketDataSubjectType.INSTRUMENT,
        capability,
        MarketDataRequestContext(
            NOW - timedelta(days=5), NOW, fields, tuple(projections), EVIDENCE
        ),
    )
    return CapabilityRequest(capability, (item,), NOW - timedelta(days=5), NOW, fields, 864000)


def test_tradier_index_quote_has_value_without_fabricated_market() -> None:
    row = {
        "symbol": "SPX",
        "type": "index",
        "last": "5512.34",
        "bid": None,
        "ask": 0,
        "trade_date": int(NOW.timestamp() * 1000),
    }
    transport = Transport((response({"quotes": {"quote": row}}),))
    result = provider(transport).fetch(
        _spx_request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization()
    )
    assert result.error is None
    quote = result.observations[0].value
    assert isinstance(quote, Quote)
    assert quote.instrument.kind is InstrumentKind.INDEX
    assert (quote.last, quote.bid, quote.ask) == (Decimal("5512.34"), None, None)


def test_tradier_spx_chain_carries_root_and_settlement_identity() -> None:
    def row(symbol: str, root: str) -> dict[str, object]:
        return {
            "symbol": symbol,
            "underlying": "SPX",
            "root_symbol": root,
            "expiration_date": "2026-10-16",
            "strike": "5500",
            "option_type": "put",
            "bid": "40",
            "ask": "41",
        }

    rows = [row("SPX261016P05500000", "SPX"), row("SPXW261016P05500000", "SPXW")]
    transport = Transport((response({"options": {"option": rows}}),))
    result = provider(transport).fetch(
        _spx_request(MarketCapability.OPTION_CHAIN_V1, ("contracts",)), authorization()
    )
    assert result.error is None
    chain = result.observations[0].value
    assert isinstance(chain, OptionChain)
    assert chain.underlying.asset_type is SecurityAssetType.INDEX
    styles = {item.root: item.settlement_style for item in chain.contracts}
    assert styles == {"SPX": SettlementStyle.AM, "SPXW": SettlementStyle.PM}
    # Same strike, date and type: AM and PM contracts stay distinct.
    assert len({item.identity for item in chain.contracts}) == 2


def test_live_subject_for_index_symbol_is_index_kind() -> None:
    subject = build_capability_subject("SPX", MarketCapability.REAL_TIME_QUOTE_V1, NOW)
    assert subject.canonical_instrument.kind is InstrumentKind.INDEX
    equity = build_capability_subject("AAPL", MarketCapability.REAL_TIME_QUOTE_V1, NOW)
    assert equity.canonical_instrument.kind is InstrumentKind.EQUITY


def test_settlement_value_uses_the_financial_wire_inside_market_data() -> None:
    from domain.market_data import _decode, _wire

    soq = IndexSettlementValue(
        SPX_SECURITY, date(2026, 10, 16), SettlementStyle.AM, Decimal("5501.23"), NOW, EVIDENCE
    )
    encoded = _wire(soq)
    assert isinstance(encoded, dict) and set(encoded) == {"$financial_contract"}
    assert _decode(encoded) == soq


def test_zero_index_level_is_no_value_not_a_price() -> None:
    row = {
        "symbol": "SPX",
        "last": "0",
        "bid": 0,
        "ask": 0,
        "trade_date": int(NOW.timestamp() * 1000),
    }
    transport = Transport((response({"quotes": {"quote": row}}),))
    result = provider(transport).fetch(
        _spx_request(MarketCapability.REAL_TIME_QUOTE_V1, ("last",)), authorization()
    )
    assert result.observations == ()
    assert result.error is not None


def test_settlement_value_has_no_provider_and_is_typed_unavailable() -> None:
    from domain.values import DomainInvariantError as InvariantError
    from market_data.alpha_vantage import ALPHA_VANTAGE_CAPABILITIES
    from market_data.finnhub import FINNHUB_CAPABILITIES
    from market_data.fixture import FIXTURE_CAPABILITIES
    from market_data.registry import ProviderPriority, ProviderPriorityPolicy
    from market_data.tradier import TRADIER_CAPABILITIES
    from screening.live_context import classify_domain_invariant_error

    declared = {
        *TRADIER_CAPABILITIES,
        *FINNHUB_CAPABILITIES,
        *ALPHA_VANTAGE_CAPABILITIES,
        *FIXTURE_CAPABILITIES,
    }
    capability = MarketCapability.INDEX_SETTLEMENT_VALUE_V1
    assert capability not in declared
    policy = ProviderPriorityPolicy(
        "test",
        tuple(ProviderPriority(item, ("p",)) for item in sorted(declared, key=lambda c: c.value)),
    )
    with pytest.raises(InvariantError) as raised:
        policy.for_capability(capability)
    assert classify_domain_invariant_error(raised.value, capability, "SPX").startswith(
        "no enabled provider declares"
    )


def test_explicit_null_settlement_style_is_a_serialization_error() -> None:
    import json

    from domain import FinancialContractSerializationError

    data = json.loads(serialize_financial_contract(_contract(root="SPX")))
    data["fields"]["settlement_style"] = None
    with pytest.raises(FinancialContractSerializationError):
        deserialize_financial_contract(json.dumps(data, sort_keys=True).encode())
