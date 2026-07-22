from __future__ import annotations

import pytest

from analytics.errors import DuplicateFeatureRegistrationError, UnknownFeatureIdError
from analytics.registry import AnalyticsFeatureDefinition, AnalyticsRegistry
from domain import MarketCapability


def _definition(
    feature_id: str = "days_to_expiration",
    feature_version: str = "1.0.0",
    description: str = "Calendar days between as-of and a given expiration date.",
    required_capabilities: tuple[MarketCapability, ...] = (MarketCapability.OPTION_CHAIN_V1,),
) -> AnalyticsFeatureDefinition:
    return AnalyticsFeatureDefinition(
        feature_id, feature_version, description, required_capabilities
    )


class TestAnalyticsFeatureDefinition:
    def test_valid_definition_constructs(self) -> None:
        definition = _definition()
        assert definition.feature_id == "days_to_expiration"

    @pytest.mark.parametrize("field", ["feature_id", "feature_version", "description"])
    def test_empty_text_field_rejected(self, field: str) -> None:
        kwargs: dict[str, object] = {
            "feature_id": "days_to_expiration",
            "feature_version": "1.0.0",
            "description": "Calendar days to expiration.",
            "required_capabilities": (MarketCapability.OPTION_CHAIN_V1,),
        }
        kwargs[field] = ""
        with pytest.raises(ValueError, match="normalized text"):
            AnalyticsFeatureDefinition(**kwargs)  # type: ignore[arg-type]

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


class TestAnalyticsRegistry:
    def test_empty_registry_is_valid(self) -> None:
        registry = AnalyticsRegistry()
        assert registry.registered_ids() == ()
        assert registry.definitions() == ()

    def test_construction_is_deterministic_regardless_of_input_order(self) -> None:
        a = _definition("days_to_expiration")
        b = _definition(
            "implied_volatility",
            description="Black-Scholes implied volatility from a market price.",
        )
        first = AnalyticsRegistry((a, b))
        second = AnalyticsRegistry((b, a))
        assert (
            first.registered_ids()
            == second.registered_ids()
            == ("days_to_expiration", "implied_volatility")
        )
        assert first.definitions() == second.definitions()

    def test_get_returns_the_registered_definition(self) -> None:
        definition = _definition()
        registry = AnalyticsRegistry((definition,))
        assert registry.get("days_to_expiration") is definition

    def test_get_unknown_feature_id_raises(self) -> None:
        registry = AnalyticsRegistry()
        with pytest.raises(UnknownFeatureIdError):
            registry.get("does_not_exist")

    def test_is_registered(self) -> None:
        registry = AnalyticsRegistry((_definition(),))
        assert registry.is_registered("days_to_expiration") is True
        assert registry.is_registered("implied_volatility") is False

    def test_duplicate_feature_id_registration_rejected(self) -> None:
        first = _definition(feature_id="days_to_expiration", feature_version="1.0.0")
        second = _definition(feature_id="days_to_expiration", feature_version="1.1.0")
        with pytest.raises(DuplicateFeatureRegistrationError):
            AnalyticsRegistry((first, second))
