from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from asa.application.ports.quotes import ProviderQuote, QuoteProviderResult


class DeterministicFakeQuoteProvider:
    name = "deterministic_fake"

    def __init__(self, observed_at: datetime | None = None) -> None:
        self._observed_at = observed_at

    def get_quotes(self, symbols: set[str]) -> QuoteProviderResult:
        observed_at = self._observed_at or datetime.now(UTC)
        fixtures = {"AAPL": (Decimal("189.42"), "USD")}
        quotes = tuple(
            ProviderQuote(
                symbol=symbol,
                price=fixtures[symbol][0],
                currency=fixtures[symbol][1],
                observed_at=observed_at,
                original_provider=self.name,
            )
            for symbol in sorted(symbols)
            if symbol in fixtures
        )
        return QuoteProviderResult(
            selected_provider=self.name,
            provider_request_id=f"fake-{uuid4().hex}",
            quotes=quotes,
        )
