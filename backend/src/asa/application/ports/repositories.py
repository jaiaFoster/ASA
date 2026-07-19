from typing import Protocol

from asa.domain.market import MarketObservation


class MarketObservationRepository(Protocol):
    def save_quote_observation(self, observation: MarketObservation) -> None: ...

    def latest_quote(self, symbol: str) -> MarketObservation | None: ...

    def check_health(self) -> bool: ...
