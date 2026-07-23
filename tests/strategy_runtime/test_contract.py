"""SPRINT-009/EPIC-2: StrategyContract validation."""

from __future__ import annotations

import pytest

from domain import MarketCapability
from strategy_runtime import (
    NO_LIFECYCLE,
    DataRequirement,
    LifecycleDeclaration,
    LifecycleModel,
    OutputKind,
    RequirementCategory,
    StrategyContract,
    StrategyContractError,
    StructureKind,
)


def _requirement(
    category: RequirementCategory = RequirementCategory.MARKET_DATA,
) -> DataRequirement:
    return DataRequirement(category, capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,))


def _contract(**overrides: object) -> StrategyContract:
    defaults: dict[str, object] = {
        "strategy_id": "example_strategy",
        "version": "1.0.0",
        "category": "options",
        "description": "An example strategy for contract validation tests.",
        "requirements": (_requirement(),),
        "lifecycle": NO_LIFECYCLE,
        "structure": StructureKind.NONE,
        "outputs": (OutputKind.METRICS,),
    }
    defaults.update(overrides)
    return StrategyContract(**defaults)  # type: ignore[arg-type]


class TestDataRequirement:
    def test_capability_backed_category_without_a_capability_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="must declare at least one"):
            DataRequirement(RequirementCategory.OPTION_DATA)

    def test_custom_category_without_an_identifier_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="custom DataRequirement"):
            DataRequirement(RequirementCategory.CUSTOM)

    def test_custom_category_with_an_identifier_is_accepted(self) -> None:
        requirement = DataRequirement(RequirementCategory.CUSTOM, identifier="proprietary_signal")
        assert requirement.identifier == "proprietary_signal"

    def test_fundamentals_category_is_declarable_with_no_capability_system_yet(self) -> None:
        # Not capability-backed today (no MarketCapability exists for it),
        # so it is declarable with neither capabilities nor an identifier --
        # future-proofing without inventing an unused data model now.
        requirement = DataRequirement(RequirementCategory.FUNDAMENTALS)
        assert requirement.capabilities == ()

    def test_duplicate_capabilities_are_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="unique"):
            DataRequirement(
                RequirementCategory.MARKET_DATA,
                capabilities=(
                    MarketCapability.REAL_TIME_QUOTE_V1,
                    MarketCapability.REAL_TIME_QUOTE_V1,
                ),
            )


class TestLifecycleDeclaration:
    def test_none_model_rejects_supported_states(self) -> None:
        with pytest.raises(StrategyContractError, match="NONE LifecycleDeclaration"):
            LifecycleDeclaration(LifecycleModel.NONE, supported_states=("watching",))

    def test_opportunity_model_requires_supported_states(self) -> None:
        with pytest.raises(StrategyContractError, match="at least one supported state"):
            LifecycleDeclaration(LifecycleModel.OPPORTUNITY, observation_type="spread")

    def test_opportunity_model_requires_observation_type(self) -> None:
        with pytest.raises(StrategyContractError, match="observation_type"):
            LifecycleDeclaration(LifecycleModel.OPPORTUNITY, supported_states=("watching",))

    def test_opportunity_model_rejects_duplicate_states(self) -> None:
        with pytest.raises(StrategyContractError, match="unique"):
            LifecycleDeclaration(
                LifecycleModel.OPPORTUNITY,
                supported_states=("watching", "watching"),
                observation_type="spread",
            )

    def test_valid_opportunity_declaration_is_accepted(self) -> None:
        declaration = LifecycleDeclaration(
            LifecycleModel.OPPORTUNITY,
            supported_states=("watching", "confirmed", "closed"),
            observation_type="calendar_spread",
        )
        assert declaration.supported_states == ("watching", "confirmed", "closed")


class TestStrategyContract:
    def test_empty_requirements_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="requirements cannot be empty"):
            _contract(requirements=())

    def test_duplicate_requirements_are_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="must not repeat"):
            _contract(requirements=(_requirement(), _requirement()))

    def test_empty_outputs_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="outputs cannot be empty"):
            _contract(outputs=())

    def test_duplicate_outputs_are_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="outputs must be unique"):
            _contract(outputs=(OutputKind.METRICS, OutputKind.METRICS))

    def test_lifecycle_output_without_an_opportunity_lifecycle_model_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="non-NONE lifecycle_model"):
            _contract(outputs=(OutputKind.LIFECYCLE,), lifecycle=NO_LIFECYCLE)

    def test_lifecycle_output_with_an_opportunity_lifecycle_model_is_accepted(self) -> None:
        contract = _contract(
            outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
            lifecycle=LifecycleDeclaration(
                LifecycleModel.OPPORTUNITY,
                supported_states=("watching", "closed"),
                observation_type="spread",
            ),
        )
        assert OutputKind.LIFECYCLE in contract.outputs

    def test_blank_metadata_fields_are_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="strategy_id"):
            _contract(strategy_id="  ")

    def test_required_capabilities_deduplicates_across_requirements(self) -> None:
        contract = _contract(
            requirements=(
                DataRequirement(
                    RequirementCategory.MARKET_DATA,
                    capabilities=(MarketCapability.REAL_TIME_QUOTE_V1,),
                ),
                DataRequirement(
                    RequirementCategory.OPTION_DATA,
                    capabilities=(
                        MarketCapability.OPTION_CHAIN_V1,
                        MarketCapability.REAL_TIME_QUOTE_V1,
                    ),
                ),
            )
        )
        assert contract.required_capabilities() == (
            MarketCapability.OPTION_CHAIN_V1,
            MarketCapability.REAL_TIME_QUOTE_V1,
        )

    def test_requirements_in_filters_by_category(self) -> None:
        option_requirement = DataRequirement(
            RequirementCategory.OPTION_DATA, capabilities=(MarketCapability.OPTION_CHAIN_V1,)
        )
        contract = _contract(requirements=(_requirement(), option_requirement))
        assert contract.requirements_in(RequirementCategory.OPTION_DATA) == (option_requirement,)
        assert contract.requirements_in(RequirementCategory.EARNINGS) == ()
