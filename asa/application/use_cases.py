import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from asa.application.ports.quotes import QuoteProvider
from asa.application.ports.repositories import MarketObservationRepository
from asa.contracts.market import CacheStatus, FreshnessStatus, MarketObservation, QuoteProvenance

Clock = Callable[[], datetime]


class MarketQuoteService:
    def __init__(
        self,
        provider: QuoteProvider,
        repository: MarketObservationRepository,
        fresh_for: timedelta,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._fresh_for = fresh_for
        self._clock = clock
        self._logger = logging.getLogger("asa.market")

    def ingest_quotes(self, symbols: set[str]) -> list[MarketObservation]:
        normalized_symbols = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
        result = self._provider.get_quotes(normalized_symbols)
        received_at = self._clock()
        observations: list[MarketObservation] = []
        for quote in result.quotes:
            observation = MarketObservation(
                symbol=quote.symbol.strip().upper(),
                price=quote.price,
                currency=quote.currency.strip().upper(),
                observed_at=quote.observed_at.astimezone(UTC),
                received_at=received_at,
                provenance=QuoteProvenance(
                    selected_provider=result.selected_provider,
                    original_provider=quote.original_provider,
                    cache_status=CacheStatus.MISS,
                    freshness_status=FreshnessStatus.STALE,
                    fallback_reason=result.fallback_reason,
                    provider_request_id=result.provider_request_id,
                ),
            ).with_current_freshness(received_at, self._fresh_for)
            self._repository.save_quote_observation(observation)
            self._logger.info(
                "quote_observation_saved",
                extra={
                    "provider_request_id": result.provider_request_id,
                    "symbol": observation.symbol,
                    "provider": result.selected_provider,
                },
            )
            observations.append(observation)
        return observations

    def get_latest_quote(self, symbol: str) -> MarketObservation | None:
        observation = self._repository.latest_quote(symbol.strip().upper())
        if observation is None:
            return None
        persisted = replace(
            observation,
            provenance=replace(observation.provenance, cache_status=CacheStatus.PERSISTED),
        )
        return persisted.with_current_freshness(self._clock(), self._fresh_for)
