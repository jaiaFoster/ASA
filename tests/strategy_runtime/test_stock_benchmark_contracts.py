from domain import MarketCapability
from strategy_runtime.adapters.stock_benchmarks import B001_CONTRACT, B002_CONTRACT
from strategy_runtime.contract import LifecycleModel, StrategyCapability, StructureKind


def test_b001_contract_uses_only_current_quote_without_option_or_lifecycle_authority() -> None:
    assert B001_CONTRACT.strategy_id == "B001"
    assert B001_CONTRACT.version == "1.0.0"
    assert B001_CONTRACT.required_capabilities() == (
        MarketCapability.REAL_TIME_QUOTE_V1,
    )
    assert B001_CONTRACT.structure is StructureKind.NONE
    assert B001_CONTRACT.lifecycle.lifecycle_model is LifecycleModel.NONE
    assert StrategyCapability.OPTION_STRUCTURES not in B001_CONTRACT.capabilities


def test_b002_contract_declares_generic_quote_and_history_only() -> None:
    assert B002_CONTRACT.strategy_id == "B002"
    assert B002_CONTRACT.version == "1.0.0"
    assert B002_CONTRACT.required_capabilities() == (
        MarketCapability.HISTORICAL_BARS_V1,
        MarketCapability.REAL_TIME_QUOTE_V1,
    )
    assert B002_CONTRACT.structure is StructureKind.NONE
    assert B002_CONTRACT.lifecycle.lifecycle_model is LifecycleModel.NONE
    assert StrategyCapability.OPTION_STRUCTURES not in B002_CONTRACT.capabilities
