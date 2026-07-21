"""STONK-004 pinned behavioral-equivalence vectors.

The expected values are transcribed from Stonk revision
5f3fec846f70e9739cf3f15695fd587f0604344c. The legacy repository is evidence,
not a runtime or test dependency.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from domain import OptionChain, OptionStructure, OptionType
from domain.execution import PortfolioDecisionState
from portfolio import evaluate_portfolio
from ranking import rank_opportunities
from strategies import (
    CalendarStructure,
    ComponentContractError,
    ForwardFactor,
    ImpliedForwardVolatility,
    OptionStructureDebit,
    VerdictClassifier,
    VerticalStructure,
)
from strategies.stonk_components import (
    D,
    DATE,
    INTEGER,
    OPTION_CHAIN,
    OPTION_STRUCTURE,
    OPTION_TYPE,
)
from strategies.type_system import ComponentValues
from tests.portfolio.helpers import request, snapshot
from tests.ranking.helpers import evaluation
from tests.strategies.test_stonk_components import (
    EVIDENCE,
    FRONT,
    NOW,
    contract,
    security,
    values,
)


def test_forward_factor_matches_legacy_reference_vector_and_replays() -> None:
    inputs = values(
        front_iv=(D, Decimal("0.48")),
        back_iv=(D, Decimal("0.4548992562461861547567860943472296")),
        front_dte=(INTEGER, 60),
        back_dte=(INTEGER, 90),
    )
    first = ImpliedForwardVolatility().evaluate(inputs, ComponentValues(()))
    second = ImpliedForwardVolatility().evaluate(inputs, ComponentValues(()))
    assert first == second
    factor = ForwardFactor().evaluate(
        values(
            front_ex_earnings_iv=(D, Decimal("0.48")),
            implied_forward_iv=(D, first.get("implied_forward_iv").value),
        ),
        ComponentValues(()),
    )
    assert factor.get("factor").value.quantize(Decimal("0.00000001")) == Decimal("0.20000000")


def test_forward_variance_fails_closed_instead_of_fabricating_a_value() -> None:
    with pytest.raises(ComponentContractError, match="forward variance"):
        ImpliedForwardVolatility().evaluate(
            values(
                front_iv=(D, Decimal("0.80")),
                back_iv=(D, Decimal("0.20")),
                front_dte=(INTEGER, 60),
                back_dte=(INTEGER, 90),
            ),
            ComponentValues(()),
        )


def test_calendar_and_vertical_prices_match_legacy_reference_vectors() -> None:
    back = FRONT.replace(month=2, day=21)
    calendar_chain = OptionChain(
        "legacy-calendar-vector",
        security(),
        NOW,
        (
            contract("calendar-front", FRONT, "100", OptionType.CALL, "0.50", "1.1"),
            contract("calendar-back", back, "100", OptionType.CALL, "0.55", "1.4"),
        ),
        EVIDENCE,
    )
    calendar = CalendarStructure().evaluate(
        values(
            chain=(OPTION_CHAIN, calendar_chain),
            front_expiration=(DATE, FRONT),
            back_expiration=(DATE, back),
            strike=(D, Decimal("100")),
        ),
        values(option_type=(OPTION_TYPE, "call")),
    )
    structure = calendar.get("structure").value
    assert isinstance(structure, OptionStructure)
    debit = OptionStructureDebit().evaluate(
        values(structure=(OPTION_STRUCTURE, structure)), ComponentValues(())
    )
    assert debit.get("mid_debit").value == Decimal("0.3")
    assert debit.get("conservative_debit").value == Decimal("0.5")

    option_chain = OptionChain(
        "legacy-vertical-vector",
        security(),
        NOW,
        (
            contract("vertical-long", FRONT, "100", OptionType.CALL, "0.55", "1.9"),
            contract("vertical-short", FRONT, "105", OptionType.CALL, "0.30", "0.8"),
        ),
        EVIDENCE,
    )
    vertical = VerticalStructure().evaluate(
        values(chain=(OPTION_CHAIN, option_chain), expiration=(DATE, FRONT)),
        values(
            option_type=(OPTION_TYPE, "call"),
            long_delta_target=(D, Decimal("0.55")),
            short_delta_target=(D, Decimal("0.30")),
        ),
    )
    vertical_structure = vertical.get("structure").value
    assert isinstance(vertical_structure, OptionStructure)
    assert tuple(leg.contract.strike for leg in vertical_structure.legs) == (
        Decimal("100"),
        Decimal("105"),
    )
    vertical_debit = OptionStructureDebit().evaluate(
        values(structure=(OPTION_STRUCTURE, vertical_structure)), ComponentValues(())
    )
    assert vertical_debit.get("conservative_debit").value == Decimal("1.3")


@pytest.mark.parametrize(
    ("score", "expected"),
    (("70", "PASS"), ("55", "WATCH"), ("54.999", "FAIL")),
)
def test_legacy_candidate_threshold_boundaries_are_preserved(score: str, expected: str) -> None:
    result = VerdictClassifier().evaluate(
        values(score=(D, Decimal(score))),
        values(
            pass_threshold=(D, Decimal("70")),
            watch_threshold=(D, Decimal("55")),
        ),
    )
    assert result.get("verdict").value == expected


def test_ranking_and_portfolio_construction_remain_owned_by_asa_engines() -> None:
    ranked = rank_opportunities(
        (
            evaluation("lower", expected_return="0.05"),
            evaluation("higher", expected_return="0.30"),
        )
    )
    assert tuple(item.opportunity.opportunity_id for item in ranked.ranked_opportunities) == (
        "higher",
        "lower",
    )
    first = evaluate_portfolio(request(snapshot()))
    replay = evaluate_portfolio(request(snapshot()))
    assert first == replay
    assert first[0].state is PortfolioDecisionState.ACCEPT


def test_equivalence_document_records_pinned_source_and_intentional_differences() -> None:
    document = (
        Path(__file__).parents[2] / "docs" / "migration" / "stonk-behavioral-equivalence.md"
    ).read_text(encoding="utf-8")
    assert "5f3fec846f70e9739cf3f15695fd587f0604344c" in document
    assert "Exact equivalence" in document
    assert "Intentional refinement" in document
    assert "no Stonk ranker" in document
    assert "Portfolio Engine" in document
