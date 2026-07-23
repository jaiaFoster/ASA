"""SPRINT-009/EPIC-1: StrategyRegistry registration and discovery."""

from __future__ import annotations

import pytest

from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    DuplicateStrategyRegistrationError,
    OutputKind,
    RequirementCategory,
    RuntimeContext,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    UnknownStrategyIdError,
)


def _contract(strategy_id: str) -> StrategyContract:
    return StrategyContract(
        strategy_id=strategy_id,
        version="1.0.0",
        category="test",
        description="A test contract.",
        requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
        lifecycle=NO_LIFECYCLE,
        structure=StructureKind.NONE,
        outputs=(OutputKind.METRICS,),
    )


def _adapter(context: RuntimeContext) -> str:
    return f"{context.contract.strategy_id}:{context.subject}"


class TestStrategyRegistry:
    def test_empty_registry_has_no_strategy_ids(self) -> None:
        registry: StrategyRegistry[str] = StrategyRegistry()
        assert registry.strategy_ids() == ()

    def test_registration_is_discoverable(self) -> None:
        registry = StrategyRegistry(((_contract("beta"), _adapter), (_contract("alpha"), _adapter)))
        assert registry.strategy_ids() == ("alpha", "beta")  # sorted, not insertion order
        assert registry.is_registered("alpha")
        assert not registry.is_registered("gamma")

    def test_duplicate_strategy_id_is_rejected(self) -> None:
        with pytest.raises(DuplicateStrategyRegistrationError, match="alpha"):
            StrategyRegistry(((_contract("alpha"), _adapter), (_contract("alpha"), _adapter)))

    def test_contract_for_unregistered_strategy_raises(self) -> None:
        registry: StrategyRegistry[str] = StrategyRegistry()
        with pytest.raises(UnknownStrategyIdError):
            registry.contract_for("nonexistent")

    def test_adapter_for_unregistered_strategy_raises(self) -> None:
        registry: StrategyRegistry[str] = StrategyRegistry()
        with pytest.raises(UnknownStrategyIdError):
            registry.adapter_for("nonexistent")

    def test_contract_for_and_adapter_for_return_the_registered_pair(self) -> None:
        contract = _contract("alpha")
        registry = StrategyRegistry(((contract, _adapter),))
        assert registry.contract_for("alpha") is contract
        assert registry.adapter_for("alpha") is _adapter

    def test_contracts_returns_every_registered_contract_sorted(self) -> None:
        registry = StrategyRegistry(((_contract("beta"), _adapter), (_contract("alpha"), _adapter)))
        assert [item.strategy_id for item in registry.contracts()] == ["alpha", "beta"]
