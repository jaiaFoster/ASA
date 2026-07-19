from asa.domain.market import MarketObservation


class InMemoryObservationRepository:
    def __init__(self, healthy: bool = True) -> None:
        self.observations: list[MarketObservation] = []
        self.healthy = healthy

    def save_quote_observation(self, observation: MarketObservation) -> None:
        self.observations.append(observation)

    def latest_quote(self, symbol: str) -> MarketObservation | None:
        matching = [item for item in self.observations if item.symbol == symbol]
        return max(matching, key=lambda item: item.observed_at) if matching else None

    def check_health(self) -> bool:
        return self.healthy
