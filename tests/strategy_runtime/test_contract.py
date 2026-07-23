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
    StrategyCapability,
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


class TestStrategyCapability:
    """SPRINT-009R/EPIC-R1: capabilities are additive and one-directional --
    a contract omitting ``capabilities`` entirely is never itself rejected
    (every pre-EPIC-R1 contract omits it), only a capability claim that
    outruns its backing declaration is.
    """

    def test_duplicate_capabilities_are_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="capabilities must be unique"):
            _contract(
                capabilities=(StrategyCapability.ECONOMICS, StrategyCapability.ECONOMICS),
                outputs=(OutputKind.METRICS, OutputKind.ECONOMICS),
            )

    def test_omitting_capabilities_on_a_legacy_style_contract_is_accepted(self) -> None:
        contract = _contract(outputs=(OutputKind.METRICS, OutputKind.ECONOMICS))
        assert contract.capabilities == ()

    def test_lifecycle_capability_without_lifecycle_output_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="StrategyCapability.LIFECYCLE"):
            _contract(
                capabilities=(StrategyCapability.LIFECYCLE,),
                outputs=(OutputKind.METRICS,),
                lifecycle=LifecycleDeclaration(
                    LifecycleModel.OPPORTUNITY,
                    supported_states=("watching",),
                    observation_type="spread",
                ),
            )

    def test_lifecycle_capability_with_lifecycle_output_and_model_is_accepted(self) -> None:
        contract = _contract(
            capabilities=(StrategyCapability.LIFECYCLE,),
            outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
            lifecycle=LifecycleDeclaration(
                LifecycleModel.OPPORTUNITY,
                supported_states=("watching",),
                observation_type="spread",
            ),
        )
        assert StrategyCapability.LIFECYCLE in contract.capabilities

    def test_history_capability_without_lifecycle_capability_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="StrategyCapability.HISTORY"):
            _contract(
                capabilities=(StrategyCapability.HISTORY,),
                outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
                lifecycle=LifecycleDeclaration(
                    LifecycleModel.OPPORTUNITY,
                    supported_states=("watching",),
                    observation_type="spread",
                ),
            )

    def test_history_capability_with_lifecycle_capability_is_accepted(self) -> None:
        contract = _contract(
            capabilities=(StrategyCapability.LIFECYCLE, StrategyCapability.HISTORY),
            outputs=(OutputKind.METRICS, OutputKind.LIFECYCLE),
            lifecycle=LifecycleDeclaration(
                LifecycleModel.OPPORTUNITY,
                supported_states=("watching",),
                observation_type="spread",
            ),
        )
        assert StrategyCapability.HISTORY in contract.capabilities

    def test_economics_capability_without_economics_output_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="StrategyCapability.ECONOMICS"):
            _contract(capabilities=(StrategyCapability.ECONOMICS,), outputs=(OutputKind.METRICS,))

    def test_recommendations_capability_without_recommendation_output_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="StrategyCapability.RECOMMENDATIONS"):
            _contract(
                capabilities=(StrategyCapability.RECOMMENDATIONS,), outputs=(OutputKind.METRICS,)
            )

    def test_recommendations_capability_with_recommendation_output_is_accepted(self) -> None:
        contract = _contract(
            capabilities=(StrategyCapability.RECOMMENDATIONS,),
            outputs=(OutputKind.METRICS, OutputKind.RECOMMENDATION_SUPPORT),
        )
        assert StrategyCapability.RECOMMENDATIONS in contract.capabilities

    def test_option_structures_capability_without_a_structure_is_rejected(self) -> None:
        with pytest.raises(StrategyContractError, match="StrategyCapability.OPTION_STRUCTURES"):
            _contract(
                capabilities=(StrategyCapability.OPTION_STRUCTURES,), structure=StructureKind.NONE
            )

    def test_option_structures_capability_with_a_structure_is_accepted(self) -> None:
        contract = _contract(
            capabilities=(StrategyCapability.OPTION_STRUCTURES,), structure=StructureKind.VERTICAL
        )
        assert StrategyCapability.OPTION_STRUCTURES in contract.capabilities

    def test_multiple_results_and_incremental_refresh_have_no_required_backing(self) -> None:
        contract = _contract(
            capabilities=(
                StrategyCapability.MULTIPLE_RESULTS,
                StrategyCapability.INCREMENTAL_REFRESH,
            )
        )
        assert contract.capabilities == (
            StrategyCapability.MULTIPLE_RESULTS,
            StrategyCapability.INCREMENTAL_REFRESH,
        )
