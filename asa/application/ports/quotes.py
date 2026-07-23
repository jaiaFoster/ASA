from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProviderQuote:
    symbol: str
    price: Decimal
    currency: str
    observed_at: datetime
    original_provider: str


@dataclass(frozen=True, slots=True)
class QuoteProviderResult:
    selected_provider: str
    provider_request_id: str
    quotes: tuple[ProviderQuote, ...]
    fallback_reason: str | None = None


class QuoteProvider(Protocol):
    def get_quotes(self, symbols: set[str]) -> QuoteProviderResult: ...
