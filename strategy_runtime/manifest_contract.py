"""Mechanical consistency boundary from canonical manifests to runtime contracts."""

from __future__ import annotations

from domain import MarketCapability
from strategies.manifest import StrategyManifest
from strategy_runtime.contract import StrategyContract
from strategy_runtime.errors import StrategyContractError


def validate_manifest_contract(
    manifest: StrategyManifest, contract: StrategyContract
) -> None:
    """Reject independently authored runtime semantics that drift from a manifest."""
    if contract.strategy_id != manifest.strategy_id:
        raise StrategyContractError(
            "runtime contract strategy_id must equal canonical manifest strategy_id"
        )
    if contract.version != manifest.strategy_version:
        raise StrategyContractError(
            "runtime contract version must equal canonical manifest strategy_version"
        )
    try:
        manifest_capabilities = tuple(
            sorted(
                (
                    MarketCapability(item.name)
                    for item in manifest.required_market_capabilities
                ),
                key=lambda item: item.value,
            )
        )
    except ValueError as exc:
        raise StrategyContractError(
            "canonical manifest declares an unknown market capability"
        ) from exc
    if contract.required_capabilities() != manifest_capabilities:
        raise StrategyContractError(
            "runtime contract capabilities must equal canonical manifest capabilities"
        )
