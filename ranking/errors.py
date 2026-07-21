"""Ranking Engine errors (ASA-CORE-007)."""

from __future__ import annotations


class RankingError(Exception):
    """Base error for deterministic ranking operations."""


class InvalidRankingParameterError(RankingError):
    """A ranking policy parameter violates the v1 scoring contract."""


class DuplicateScorerRegistrationError(RankingError):
    def __init__(self, dimension: str) -> None:
        super().__init__(f"ranking dimension already registered: {dimension!r}")
        self.dimension = dimension


class UnknownScoringDimensionError(RankingError):
    def __init__(self, dimension: str) -> None:
        super().__init__(f"no scorer registered for dimension: {dimension!r}")
        self.dimension = dimension


class InvalidScorerRegistryError(RankingError):
    """The active registry does not contain exactly the pinned v1 dimensions."""


class InvalidScorerOutputError(RankingError):
    """A scorer returned provenance inconsistent with its registry definition."""


class InvalidRankingOutputError(RankingError):
    """A RankedOpportunity or RankingResult violates the pinned output contract."""


class DuplicateOpportunityEvaluationError(RankingError):
    def __init__(self, opportunity_id: str) -> None:
        super().__init__(f"multiple evaluations supplied for opportunity: {opportunity_id!r}")
        self.opportunity_id = opportunity_id
