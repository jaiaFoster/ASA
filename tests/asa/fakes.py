from asa.contracts.market import MarketObservation
from screening.state import ScreeningStateRecord
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


class InMemoryScreeningStateRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], ScreeningStateRecord] = {}

    def upsert(self, record: ScreeningStateRecord) -> None:
        self._records[(record.signal_id, record.symbol)] = record

    def get_all(self) -> tuple[ScreeningStateRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda item: (item.signal_id, item.symbol)))

    def get_for_signal(self, signal_id: str) -> tuple[ScreeningStateRecord, ...]:
        return tuple(
            sorted(
                (record for record in self._records.values() if record.signal_id == signal_id),
                key=lambda item: item.symbol,
            )
        )

    def get_one(self, signal_id: str, symbol: str) -> ScreeningStateRecord | None:
        return self._records.get((signal_id, symbol))


class InMemoryLatestResultRepository:
    """SPRINT-009R/EPIC-R5: the strategy_runtime-backed equivalent of
    InMemoryScreeningStateRepository above, over UniversalSignalRow instead
    of ScreeningStateRecord -- same upsert/get_all/get_for_signal/get_one
    shape, matching strategy_runtime.persistence.LatestResultRepository.
    """

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
