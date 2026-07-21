"""Deterministic Ranking Layer (ASA-CORE-007)."""

from ranking.engine import rank_opportunities, ranking_identity
from ranking.errors import (
    DuplicateOpportunityEvaluationError,
    DuplicateScorerRegistrationError,
    InvalidRankingParameterError,
    InvalidRankingOutputError,
    InvalidScorerOutputError,
    InvalidScorerRegistryError,
    RankingError,
    UnknownScoringDimensionError,
)
from ranking.models import (
    RANKING_ALGORITHM_VERSION,
    RANKING_DIMENSIONS,
    RankedOpportunity,
    RankingParameters,
    RankingResult,
    ScoreComponent,
)
from ranking.registry import DEFAULT_REGISTRY, ScorerRegistry

__all__ = [
    "DEFAULT_REGISTRY",
    "DuplicateOpportunityEvaluationError",
    "DuplicateScorerRegistrationError",
    "InvalidRankingParameterError",
    "InvalidRankingOutputError",
    "InvalidScorerOutputError",
    "InvalidScorerRegistryError",
    "RANKING_ALGORITHM_VERSION",
    "RANKING_DIMENSIONS",
    "RankedOpportunity",
    "RankingError",
    "RankingParameters",
    "RankingResult",
    "ScoreComponent",
    "ScorerRegistry",
    "UnknownScoringDimensionError",
    "rank_opportunities",
    "ranking_identity",
]
