"""Pure deterministic Position Proposal Engine (ASA-CORE-008)."""

from __future__ import annotations

import hashlib
from decimal import Decimal, localcontext

from domain.canonicalization import serialize_canonical
from domain.operational import ProposedPosition
from domain.references import EvidenceReference
from position_proposals.models import (
    ALLOCATION_QUANTUM,
    PROPOSAL_ALGORITHM_VERSION,
    PROPOSAL_IDENTITY_NAMESPACE,
    ProposalParameters,
)
from ranking.models import RankedOpportunity, RankingResult


def _evidence_identity(reference: EvidenceReference) -> tuple[object, ...]:
    return (reference.kind.value, reference.referenced_id, reference.version)


def _proposal_evidence(ranked: RankedOpportunity) -> tuple[EvidenceReference, ...]:
    references = ranked.opportunity.evidence + ranked.opportunity.supporting_indicators
    unique = {
        (reference.kind.value, reference.referenced_id, reference.version): reference
        for reference in references
    }
    return tuple(unique[key] for key in sorted(unique))


def _target_allocation(score: Decimal, parameters: ProposalParameters) -> Decimal:
    with localcontext() as context:
        context.prec = 40
        spread = parameters.allocation_ceiling - parameters.allocation_floor
        return (parameters.allocation_floor + spread * score).quantize(ALLOCATION_QUANTUM)


def proposed_position_identity(
    ranking_result_id: str,
    ranked: RankedOpportunity,
    target_allocation: Decimal,
    effective_parameters: tuple[tuple[str, Decimal], ...],
    rationale: tuple[str, ...],
    evidence: tuple[EvidenceReference, ...],
) -> str:
    """Return the content identity for one v1 ProposedPosition."""
    instrument = ranked.opportunity.instrument
    payload = "\n".join(
        (
            PROPOSAL_IDENTITY_NAMESPACE,
            PROPOSAL_ALGORITHM_VERSION,
            serialize_canonical(ranking_result_id),
            serialize_canonical(ranked.ranking_id),
            serialize_canonical(ranked.opportunity.opportunity_id),
            serialize_canonical((instrument.identity.scheme, instrument.identity.value)),
            serialize_canonical(target_allocation),
            serialize_canonical(Decimal(str(ranked.opportunity.evidence_confidence.score))),
            serialize_canonical(rationale),
            serialize_canonical(effective_parameters),
            serialize_canonical(tuple(_evidence_identity(item) for item in evidence)),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def propose_positions(
    ranking_result: RankingResult,
    parameters: ProposalParameters | None = None,
) -> tuple[ProposedPosition, ...]:
    """Convert ranked Opportunities to desired allocations in rank order.

    This function has no PortfolioSnapshot, Holding, account, price, quantity,
    provider, repository, persistence, or network input. Allocation is a pure
    linear interpolation of the pinned Ranking score within explicit policy
    bounds; Portfolio policy may accept, reduce, reject, or hold it later.
    """
    parameters = parameters or ProposalParameters()
    effective_parameters = parameters.canonical_items()
    proposals: list[ProposedPosition] = []
    for ranked in ranking_result.ranked_opportunities:
        target_allocation = _target_allocation(ranked.total_score, parameters)
        rationale = (
            f"{PROPOSAL_ALGORITHM_VERSION} allocation from ranking score {ranked.total_score}",
            *ranked.opportunity.assumptions,
        )
        evidence = _proposal_evidence(ranked)
        proposals.append(
            ProposedPosition(
                proposed_position_id=proposed_position_identity(
                    ranking_result.result_id,
                    ranked,
                    target_allocation,
                    effective_parameters,
                    rationale,
                    evidence,
                ),
                opportunity_id=ranked.opportunity.opportunity_id,
                ranking_result_id=ranking_result.result_id,
                ranking_id=ranked.ranking_id,
                proposal_algorithm_version=PROPOSAL_ALGORITHM_VERSION,
                instrument=ranked.opportunity.instrument,
                target_allocation=target_allocation,
                evidence_confidence=ranked.opportunity.evidence_confidence,
                rationale=rationale,
                effective_parameters=effective_parameters,
                evidence=evidence,
            )
        )
    return tuple(proposals)
