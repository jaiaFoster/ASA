from asa.contracts.market import MarketObservation
from strategy_runtime.lifecycle import OpportunityHistory, OpportunityObservation
from strategy_runtime.persistence import UniversalSignalRow


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


class InMemoryLatestResultRepository:
    """In-memory universal latest-result store for application tests."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], UniversalSignalRow] = {}

    def upsert(self, row: UniversalSignalRow) -> None:
        self._rows[(row.signal_id, row.symbol)] = row

    def get_all(self) -> tuple[UniversalSignalRow, ...]:
        return tuple(sorted(self._rows.values(), key=lambda item: (item.signal_id, item.symbol)))

    def get_for_signal(self, signal_id: str) -> tuple[UniversalSignalRow, ...]:
        return tuple(
            sorted(
                (row for row in self._rows.values() if row.signal_id == signal_id),
                key=lambda item: item.symbol,
            )
        )

    def get_one(self, signal_id: str, symbol: str) -> UniversalSignalRow | None:
        return self._rows.get((signal_id, symbol))


class InMemoryObservationHistoryRepository:
    def __init__(self) -> None:
        self._observations: dict[str, list[OpportunityObservation]] = {}

    def append(self, observation: OpportunityObservation) -> None:
        values = self._observations.setdefault(observation.opportunity_id, [])
        if observation not in values:
            values.append(observation)

    def history_for(self, opportunity_id: str) -> OpportunityHistory | None:
        values = self._observations.get(opportunity_id)
        return OpportunityHistory(opportunity_id, tuple(values)) if values else None
