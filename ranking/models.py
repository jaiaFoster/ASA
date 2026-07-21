"""Immutable Ranking Engine inputs, provenance, and outputs (ASA-CORE-007)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.opportunity import Opportunity
from domain.values import require_finite_decimal
from guardrails.evaluations import GuardrailDecision, OpportunityGuardrailEvaluation
from ranking.errors import InvalidRankingOutputError, InvalidRankingParameterError

RANKING_IDENTITY_NAMESPACE = "asa.ranking"
RANKING_RESULT_IDENTITY_NAMESPACE = "asa.ranking_result"
RANKING_ALGORITHM_VERSION = "v1"
SCORE_QUANTUM = Decimal("0.000000000001")

RANKING_DIMENSIONS = (
    "capital_efficiency",
    "downside_risk",
    "evidence_confidence",
    "expected_return",
    "liquidity",
    "opportunity_quality",
)


@dataclass(frozen=True, slots=True)
class RankingParameters:
    """All effective v1 scoring policy, with no hidden module-level settings."""

    expected_return_floor: Decimal = Decimal("-0.25")
    expected_return_ceiling: Decimal = Decimal("0.25")
    maximum_loss_ratio_ceiling: Decimal = Decimal("1")
    daily_return_floor: Decimal = Decimal("-0.01")
    daily_return_ceiling: Decimal = Decimal("0.01")
    liquidity_placeholder_score: Decimal = Decimal("0.5")
    quality_placeholder_score: Decimal = Decimal("0.5")
    expected_return_weight: Decimal = Decimal("1")
    downside_risk_weight: Decimal = Decimal("1")
    evidence_confidence_weight: Decimal = Decimal("1")
    capital_efficiency_weight: Decimal = Decimal("1")
    liquidity_weight: Decimal = Decimal("1")
    opportunity_quality_weight: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            try:
                require_finite_decimal(value, "RankingParameters", name)
            except (TypeError, ValueError) as error:
                raise InvalidRankingParameterError(str(error)) from error
        if self.expected_return_floor >= self.expected_return_ceiling:
            raise InvalidRankingParameterError(
                "expected_return_floor must be less than expected_return_ceiling"
            )
        if self.daily_return_floor >= self.daily_return_ceiling:
            raise InvalidRankingParameterError(
                "daily_return_floor must be less than daily_return_ceiling"
            )
        if self.maximum_loss_ratio_ceiling <= 0:
            raise InvalidRankingParameterError("maximum_loss_ratio_ceiling must be positive")
        for name in ("liquidity_placeholder_score", "quality_placeholder_score"):
            value = getattr(self, name)
            if not Decimal("0") <= value <= Decimal("1"):
                raise InvalidRankingParameterError(f"{name} must be in [0, 1]")
        weights = self.weights()
        if any(weight < 0 for _, weight in weights):
            raise InvalidRankingParameterError("ranking weights cannot be negative")
        if sum((weight for _, weight in weights), Decimal("0")) <= 0:
            raise InvalidRankingParameterError("at least one ranking weight must be positive")

    def weights(self) -> tuple[tuple[str, Decimal], ...]:
        return (
            ("capital_efficiency", self.capital_efficiency_weight),
            ("downside_risk", self.downside_risk_weight),
            ("evidence_confidence", self.evidence_confidence_weight),
            ("expected_return", self.expected_return_weight),
            ("liquidity", self.liquidity_weight),
            ("opportunity_quality", self.opportunity_quality_weight),
        )

    def canonical_items(self) -> tuple[tuple[str, Decimal], ...]:
        return tuple(sorted((name, getattr(self, name)) for name in self.__dataclass_fields__))


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    dimension: str
    scorer_version: str
    raw_value: Decimal
    score: Decimal
    effective_parameters: tuple[tuple[str, Decimal], ...]
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_finite_decimal(self.raw_value, "ScoreComponent", "raw_value")
        require_finite_decimal(self.score, "ScoreComponent", "score")
        if not Decimal("0") <= self.score <= Decimal("1"):
            raise InvalidRankingParameterError("component score must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class RankedOpportunity:
    ranking_id: str
    rank: int
    ranking_algorithm_version: str
    evaluation: OpportunityGuardrailEvaluation
    scoring_components: tuple[ScoreComponent, ...]
    total_score: Decimal
    effective_parameters: tuple[tuple[str, Decimal], ...]

    def __post_init__(self) -> None:
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise InvalidRankingOutputError("rank must be a positive integer")
        if self.ranking_algorithm_version != RANKING_ALGORITHM_VERSION:
            raise InvalidRankingOutputError("ranking algorithm version is not pinned v1")
        if self.evaluation.overall_decision is not GuardrailDecision.PASS:
            raise InvalidRankingOutputError("only PASS evaluations may be ranked")
        if tuple(item.dimension for item in self.scoring_components) != RANKING_DIMENSIONS:
            raise InvalidRankingOutputError("ranked output must contain every component in order")
        require_finite_decimal(self.total_score, "RankedOpportunity", "total_score")
        if not Decimal("0") <= self.total_score <= Decimal("1"):
            raise InvalidRankingOutputError("total score must be in [0, 1]")

    @property
    def opportunity(self) -> Opportunity:
        return self.evaluation.opportunity


@dataclass(frozen=True, slots=True)
class RankingResult:
    result_id: str
    ranking_algorithm_version: str
    ranked_opportunities: tuple[RankedOpportunity, ...]
    effective_parameters: tuple[tuple[str, Decimal], ...]

    def __post_init__(self) -> None:
        if self.ranking_algorithm_version != RANKING_ALGORITHM_VERSION:
            raise InvalidRankingOutputError("ranking result algorithm version is not pinned v1")
        expected_ranks = tuple(range(1, len(self.ranked_opportunities) + 1))
        actual_ranks = tuple(item.rank for item in self.ranked_opportunities)
        if actual_ranks != expected_ranks:
            raise InvalidRankingOutputError("ranking result ranks must be contiguous and ordered")
        opportunity_ids = tuple(
            item.opportunity.opportunity_id for item in self.ranked_opportunities
        )
        if len(opportunity_ids) != len(set(opportunity_ids)):
            raise InvalidRankingOutputError("ranking result contains duplicate Opportunities")
