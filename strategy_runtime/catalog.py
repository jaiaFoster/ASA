"""Read-only public catalog projection for universal runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass

from domain import MarketCapability
from strategy_runtime.contract import StrategyContract


@dataclass(frozen=True, slots=True)
class SignalCatalogEntry:
    signal_id: str
    signal_version: str
    manifest_id: str
    required_capabilities: tuple[MarketCapability, ...]

    @classmethod
    def from_contract(
        cls, contract: StrategyContract, *, manifest_id: str
    ) -> SignalCatalogEntry:
        capabilities = tuple(
            sorted(
                {
                    capability
                    for requirement in contract.requirements
                    for capability in requirement.capabilities
                },
                key=lambda item: item.value,
            )
        )
        return cls(
            signal_id=contract.strategy_id,
            signal_version=contract.version,
            manifest_id=manifest_id,
            required_capabilities=capabilities,
        )
