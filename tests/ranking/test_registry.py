"""Ranking scorer registry validation tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ranking.engine import rank_opportunities
from ranking.errors import (
    DuplicateScorerRegistrationError,
    InvalidScorerOutputError,
    InvalidScorerRegistryError,
    UnknownScoringDimensionError,
)
from ranking.models import RANKING_DIMENSIONS
from ranking.registry import DEFAULT_REGISTRY, ScorerRegistry
from ranking.scorers import score_liquidity
from tests.ranking.helpers import evaluation


def test_default_registry_contains_exact_required_dimensions() -> None:
    assert DEFAULT_REGISTRY.registered_dimensions() == RANKING_DIMENSIONS
    DEFAULT_REGISTRY.validate_required_dimensions()


def test_registry_lookup_is_deterministic() -> None:
    assert DEFAULT_REGISTRY.get("liquidity") is DEFAULT_REGISTRY.get("liquidity")


def test_duplicate_and_unknown_dimensions_are_rejected() -> None:
    registry = ScorerRegistry()
    registry.register("liquidity", "v1", score_liquidity)
    with pytest.raises(DuplicateScorerRegistrationError):
        registry.register("liquidity", "v1", score_liquidity)
    with pytest.raises(UnknownScoringDimensionError):
        registry.get("missing")


def test_incomplete_registry_is_rejected() -> None:
    registry = ScorerRegistry()
    registry.register("liquidity", "v1", score_liquidity)
    with pytest.raises(InvalidScorerRegistryError):
        registry.validate_required_dimensions()


def test_scorer_output_must_match_registered_provenance() -> None:
    def bad_liquidity(opportunity, parameters):  # type: ignore[no-untyped-def]
        return replace(score_liquidity(opportunity, parameters), dimension="wrong")

    registry = ScorerRegistry()
    for dimension in DEFAULT_REGISTRY.registered_dimensions():
        definition = DEFAULT_REGISTRY.get(dimension)
        scorer = definition.scorer
        if dimension == "liquidity":
            scorer = bad_liquidity
        registry.register(dimension, definition.scorer_version, scorer)
    with pytest.raises(InvalidScorerOutputError):
        rank_opportunities((evaluation("bad-scorer"),), registry=registry)
