"""Canonical index-instrument and index-option product facts (X01, SP-01A).

Provider-neutral reference data owned by market data. It answers two
questions without any strategy knowledge:

- is a subject symbol a non-tradable index (INDEX), not an equity/ETF;
- what settlement style does an index-option contract root carry.

The root → settlement mapping is the exchange's product definition (Cboe:
SPX standard options are AM-settled to the special opening quotation; SPXW
options are PM-settled). An unlisted root has no settlement style, so a
consumer that needs one sees UNKNOWN. Nothing is inferred from OCC text or
from a strategy id.
"""

from __future__ import annotations

from types import MappingProxyType

from domain import InstrumentKind, SecurityAssetType, SettlementStyle

CANONICAL_INDEX_SYMBOLS: frozenset[str] = frozenset({"SPX"})

INDEX_OPTION_SETTLEMENT_BY_ROOT = MappingProxyType(
    {
        "SPX": SettlementStyle.AM,
        "SPXW": SettlementStyle.PM,
    }
)


def canonical_instrument_kind(symbol: str) -> InstrumentKind:
    return (
        InstrumentKind.INDEX if symbol.upper() in CANONICAL_INDEX_SYMBOLS else InstrumentKind.EQUITY
    )


def security_asset_type_for(kind: InstrumentKind) -> SecurityAssetType:
    return SecurityAssetType.INDEX if kind is InstrumentKind.INDEX else SecurityAssetType.EQUITY


def index_option_settlement_style(root: str | None) -> SettlementStyle | None:
    return None if root is None else INDEX_OPTION_SETTLEMENT_BY_ROOT.get(root.upper())
