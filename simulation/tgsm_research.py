"""Research seam that delegates interpretation and allocation to production S001."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from screening.universe_membership import EffectiveUniverseMembership
from strategies.tgsm_composition import SectorFacts
from strategies.tgsm_decision import (
    DefensiveAssetEvidence,
    S001TargetDecision,
    build_s001_target_decision,
)
from strategy_runtime.adapters.tgsm_subject_first import evaluate_s001_cohort
from strategy_runtime.cohort_composition import SealedCohortKnowledge


def evaluate_tgsm_research_target(
    cohort: SealedCohortKnowledge[SectorFacts],
    membership: EffectiveUniverseMembership,
    *,
    defensive_evidence: DefensiveAssetEvidence | None,
    next_eligible_session: Callable[[datetime], datetime],
) -> S001TargetDecision:
    """Return the production S001 decision; research owns no strategy copy."""
    selection = evaluate_s001_cohort(cohort, membership)
    return build_s001_target_decision(
        selection,
        defensive_evidence=defensive_evidence,
        next_eligible_session=next_eligible_session,
    )
