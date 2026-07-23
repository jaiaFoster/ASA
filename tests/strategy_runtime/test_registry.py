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
    StrategyCapability,
    StrategyContract,
    StrategyRegistry,
    StructureKind,
    UnknownStrategyIdError,
    describe_contract,
    describe_registry,
    register,
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


class TestRegisterHelper:
    """SPRINT-009R/EPIC-R4: register() -- the ergonomic wrapper a new
    strategy's own registration site uses.
    """

    def test_register_builds_an_equivalent_registry(self) -> None:
        contract = _contract("alpha")
        registry = register((contract, _adapter))
        assert registry.strategy_ids() == ("alpha",)
        assert registry.contract_for("alpha") is contract

    def test_register_still_rejects_duplicate_strategy_ids(self) -> None:
        with pytest.raises(DuplicateStrategyRegistrationError, match="alpha"):
            register((_contract("alpha"), _adapter), (_contract("alpha"), _adapter))


class TestDescribeContractAndRegistry:
    """SPRINT-009R/EPIC-R4: runtime diagnostics for a developer registering
    a new strategy.
    """

    def test_describe_contract_names_every_dimension(self) -> None:
        contract = StrategyContract(
            strategy_id="alpha",
            version="2.0.0",
            category="options_volatility",
            description="A test contract.",
            requirements=(DataRequirement(RequirementCategory.CUSTOM, identifier="none"),),
            lifecycle=NO_LIFECYCLE,
            structure=StructureKind.NONE,
            outputs=(OutputKind.METRICS, OutputKind.ECONOMICS),
            capabilities=(StrategyCapability.ECONOMICS,),
        )

        description = describe_contract(contract)

        assert "alpha" in description
        assert "2.0.0" in description
        assert "options_volatility" in description
        assert "custom" in description
        assert "economics" in description

    def test_describe_registry_lists_every_strategy_in_order(self) -> None:
        registry = register((_contract("beta"), _adapter), (_contract("alpha"), _adapter))

        description = describe_registry(registry)

        lines = description.splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("alpha ")
        assert lines[1].startswith("beta ")

    def test_describe_registry_of_an_empty_registry_is_empty(self) -> None:
        registry: StrategyRegistry[str] = StrategyRegistry()
        assert describe_registry(registry) == ""
