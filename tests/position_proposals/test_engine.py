"""ASA-CORE-008 deterministic Position Proposal Engine tests."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from position_proposals.engine import propose_positions
from position_proposals.errors import InvalidProposalParameterError
from position_proposals.models import PROPOSAL_ALGORITHM_VERSION, ProposalParameters
from ranking.engine import rank_opportunities
from tests.instrument_helpers import TEST_INSTRUMENT
from tests.ranking.helpers import evaluation


def _ranking():  # type: ignore[no-untyped-def]
    return rank_opportunities(
        (
            evaluation("lower", expected_return="0.02", confidence=0.6),
            evaluation("higher", expected_return="0.20", confidence=0.9),
        )
    )


def test_proposes_one_position_per_ranked_opportunity_in_rank_order() -> None:
    ranking = _ranking()
    proposals = propose_positions(ranking)
    assert tuple(item.opportunity_id for item in proposals) == tuple(
        item.opportunity.opportunity_id for item in ranking.ranked_opportunities
    )
    assert len(proposals) == 2


def test_replay_is_byte_identical() -> None:
    ranking = _ranking()
    assert propose_positions(ranking) == propose_positions(ranking)


def test_input_order_cannot_change_proposals_after_ranking() -> None:
    evaluations = (
        evaluation("one", expected_return="0.02"),
        evaluation("two", expected_return="0.20"),
    )
    forward = rank_opportunities(evaluations)
    backward = rank_opportunities(tuple(reversed(evaluations)))
    assert propose_positions(forward) == propose_positions(backward)


def test_instrument_confidence_rationale_and_evidence_are_propagated() -> None:
    ranking = _ranking()
    ranked = ranking.ranked_opportunities[0]
    proposal = propose_positions(ranking)[0]
    assert proposal.instrument is ranked.opportunity.instrument is TEST_INSTRUMENT
    assert proposal.evidence_confidence is ranked.opportunity.evidence_confidence
    assert ranked.opportunity.assumptions[0] in proposal.rationale
    assert proposal.evidence
    assert proposal.expected_outcome_metrics is ranked.opportunity.expected_outcome_metrics
    assert proposal.strategy_risk_policies == ranked.opportunity.strategy_risk_policies


def test_allocation_is_bounded_and_monotonic_with_score() -> None:
    proposals = propose_positions(_ranking())
    assert Decimal("0.01") <= proposals[1].target_allocation
    assert proposals[0].target_allocation <= Decimal("0.10")
    assert proposals[0].target_allocation > proposals[1].target_allocation


def test_policy_version_and_all_effective_parameters_are_recorded() -> None:
    proposal = propose_positions(_ranking())[0]
    assert proposal.proposal_algorithm_version == PROPOSAL_ALGORITHM_VERSION == "v1"
    assert proposal.effective_parameters == (
        ("allocation_ceiling", Decimal("0.10")),
        ("allocation_floor", Decimal("0.01")),
    )


def test_v1_regression_vector_pins_allocation_and_identity() -> None:
    proposals = propose_positions(_ranking())
    assert tuple((item.target_allocation, item.proposed_position_id) for item in proposals) == (
        (
            Decimal("0.083500000000"),
            "d3e56014ca9ec4e41f7afda92bd2c746a59559ac8bcaf9f18a4afbc6894c548d",
        ),
        (
            Decimal("0.067600000000"),
            "9326053ee2d05821eff2e7d36087247a3ac477a777e97f671d8796f8e8fd1262",
        ),
    )


def test_policy_change_changes_allocation_and_identity() -> None:
    ranking = _ranking()
    baseline = propose_positions(ranking)[0]
    changed = propose_positions(
        ranking,
        ProposalParameters(
            allocation_floor=Decimal("0.02"),
            allocation_ceiling=Decimal("0.20"),
        ),
    )[0]
    assert baseline.target_allocation != changed.target_allocation
    assert baseline.proposed_position_id != changed.proposed_position_id


def test_output_is_immutable() -> None:
    proposal = propose_positions(_ranking())[0]
    with pytest.raises(Exception):
        proposal.target_allocation = Decimal("0.5")


def test_empty_ranking_produces_no_proposals() -> None:
    empty = rank_opportunities(())
    assert propose_positions(empty) == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"allocation_floor": Decimal("0")},
        {"allocation_ceiling": Decimal("1.1")},
        {"allocation_floor": Decimal("0.2"), "allocation_ceiling": Decimal("0.1")},
    ],
)
def test_invalid_policy_parameters_are_rejected(changes: dict[str, Decimal]) -> None:
    with pytest.raises(InvalidProposalParameterError):
        replace(ProposalParameters(), **changes)
