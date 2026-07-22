import dataclasses

from domain.simulation import (
    SimulatedFill,
    SimulatedOrderState,
    SimulationFrame,
    SimulationMarketData,
    SimulationResult,
    SimulationTraceEvent,
)


def test_simulation_contracts_are_immutable() -> None:
    for contract in (
        SimulationFrame, SimulationMarketData, SimulatedFill,
        SimulatedOrderState, SimulationTraceEvent, SimulationResult,
    ):
        assert dataclasses.is_dataclass(contract)
        assert contract.__dataclass_params__.frozen
