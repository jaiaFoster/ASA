"""Explicit deterministic scoring registry (ASA-CORE-007)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from domain.opportunity import Opportunity
from ranking.errors import (
    DuplicateScorerRegistrationError,
    InvalidScorerRegistryError,
    UnknownScoringDimensionError,
)
from ranking.models import RANKING_DIMENSIONS, RankingParameters, ScoreComponent
from ranking.scorers import (
    SCORER_VERSION,
    score_capital_efficiency,
    score_downside_risk,
    score_evidence_confidence,
    score_expected_return,
    score_liquidity,
    score_opportunity_quality,
)

Scorer = Callable[[Opportunity, RankingParameters], ScoreComponent]


@dataclass(frozen=True, slots=True)
class ScorerDefinition:
    dimension: str
    scorer_version: str
    scorer: Scorer


class ScorerRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ScorerDefinition] = {}

    def register(self, dimension: str, scorer_version: str, scorer: Scorer) -> None:
        if dimension in self._definitions:
            raise DuplicateScorerRegistrationError(dimension)
        self._definitions[dimension] = ScorerDefinition(dimension, scorer_version, scorer)

    def get(self, dimension: str) -> ScorerDefinition:
        try:
            return self._definitions[dimension]
        except KeyError:
            raise UnknownScoringDimensionError(dimension) from None

    def registered_dimensions(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def validate_required_dimensions(self) -> None:
        if self.registered_dimensions() != RANKING_DIMENSIONS:
            raise InvalidScorerRegistryError(
                "ranking registry must contain exactly the pinned v1 dimensions"
            )


def build_default_registry() -> ScorerRegistry:
    registry = ScorerRegistry()
    registry.register("capital_efficiency", SCORER_VERSION, score_capital_efficiency)
    registry.register("downside_risk", SCORER_VERSION, score_downside_risk)
    registry.register("evidence_confidence", SCORER_VERSION, score_evidence_confidence)
    registry.register("expected_return", SCORER_VERSION, score_expected_return)
    registry.register("liquidity", SCORER_VERSION, score_liquidity)
    registry.register("opportunity_quality", SCORER_VERSION, score_opportunity_quality)
    registry.validate_required_dimensions()
    return registry


DEFAULT_REGISTRY = build_default_registry()
