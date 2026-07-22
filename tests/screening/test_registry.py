from __future__ import annotations

import pytest

from domain import MarketCapability
from screening.errors import DuplicateScreeningRegistrationError, UnknownScreeningStrategyIdError
from screening.registry import ScreeningRegistry, ScreeningStrategyDefinition


def _definition(
    strategy_id: str = "forward_factor",
    strategy_version: str = "1.1.0",
    manifest_id: str = "asa.stonk.forward_factor_calendar",
    required_capabilities: tuple[MarketCapability, ...] = (MarketCapability.OPTION_CHAIN_V1,),
) -> ScreeningStrategyDefinition:
    return ScreeningStrategyDefinition(
        strategy_id, strategy_version, manifest_id, required_capabilities
    )


class TestScreeningStrategyDefinition:
    def test_valid_definition_constructs(self) -> None:
        definition = _definition()
        assert definition.strategy_id == "forward_factor"
        assert definition.required_capabilities == (MarketCapability.OPTION_CHAIN_V1,)

    @pytest.mark.parametrize("field", ["strategy_id", "strategy_version", "manifest_id"])
    def test_empty_text_field_rejected(self, field: str) -> None:
        kwargs: dict[str, object] = {
            "strategy_id": "forward_factor",
            "strategy_version": "1.1.0",
            "manifest_id": "asa.stonk.forward_factor_calendar",
            "required_capabilities": (MarketCapability.OPTION_CHAIN_V1,),
        }
        kwargs[field] = ""
        with pytest.raises(ValueError, match="normalized text"):
            ScreeningStrategyDefinition(**kwargs)  # type: ignore[arg-type]

    def test_whitespace_padded_text_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="normalized text"):
            _definition(strategy_id=" forward_factor ")

    def test_empty_required_capabilities_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            _definition(required_capabilities=())

    def test_duplicate_required_capabilities_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be unique"):
            _definition(
                required_capabilities=(
                    MarketCapability.OPTION_CHAIN_V1,
                    MarketCapability.OPTION_CHAIN_V1,
                )
            )

    def test_multiple_canonical_capabilities_allowed(self) -> None:
        definition = _definition(
            strategy_id="earnings_calendar",
            manifest_id="asa.stonk.earnings_calendar",
            required_capabilities=(
                MarketCapability.EARNINGS_CALENDAR_V1,
                MarketCapability.OPTION_CHAIN_V1,
            ),
        )
        assert len(definition.required_capabilities) == 2


class TestScreeningRegistry:
    def test_empty_registry_is_valid(self) -> None:
        registry = ScreeningRegistry()
        assert registry.registered_ids() == ()
        assert registry.definitions() == ()

    def test_construction_is_deterministic_regardless_of_input_order(self) -> None:
        a = _definition("forward_factor")
        b = _definition("skew_momentum", manifest_id="asa.stonk.skew_momentum_vertical")
        first = ScreeningRegistry((a, b))
        second = ScreeningRegistry((b, a))
        assert first.registered_ids() == second.registered_ids() == ("forward_factor", "skew_momentum")
        assert first.definitions() == second.definitions()

    def test_get_returns_the_registered_definition(self) -> None:
        definition = _definition()
        registry = ScreeningRegistry((definition,))
        assert registry.get("forward_factor") is definition

    def test_get_unknown_strategy_id_raises(self) -> None:
        registry = ScreeningRegistry()
        with pytest.raises(UnknownScreeningStrategyIdError):
            registry.get("does_not_exist")

    def test_is_registered(self) -> None:
        registry = ScreeningRegistry((_definition(),))
        assert registry.is_registered("forward_factor") is True
        assert registry.is_registered("skew_momentum") is False

    def test_duplicate_strategy_id_registration_rejected(self) -> None:
        first = _definition(strategy_id="forward_factor", strategy_version="1.1.0")
        second = _definition(strategy_id="forward_factor", strategy_version="1.2.0")
        with pytest.raises(DuplicateScreeningRegistrationError):
            ScreeningRegistry((first, second))

    def test_definitions_are_returned_in_sorted_strategy_id_order(self) -> None:
        registry = ScreeningRegistry(
            (
                _definition("skew_momentum", manifest_id="asa.stonk.skew_momentum_vertical"),
                _definition("earnings_calendar", manifest_id="asa.stonk.earnings_calendar"),
                _definition("forward_factor"),
            )
        )
        assert registry.registered_ids() == ("earnings_calendar", "forward_factor", "skew_momentum")
