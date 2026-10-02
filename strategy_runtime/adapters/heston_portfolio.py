"""Heston binding onto generic P03/P12 runtime structures."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from analytics.option_returns import zero_delta_straddle_weights
from analytics.quantile_assignment import QuantilePolicy, assign_quantiles
from domain import OptionLeg, OptionLegPosition, UnknownReason
from strategies.heston_manifest import heston_parameter
from strategies.heston_portfolio import HestonSubjectCandidate
from strategies.heston_selection import (
    UNKNOWN_SELECTION_CODES,
    HestonPairSelection,
    select_heston_pair,
)
from strategy_runtime.cross_sectional_portfolio import (
    CrossSectionalPortfolio,
    PortfolioWeightPolicy,
    ZeroDeltaStraddlePosition,
    build_cross_sectional_portfolio,
)


@dataclass(frozen=True, slots=True)
class HestonSubjectMaterialization:
    state: str
    reason: str
    quantile: int | None = None
    position: ZeroDeltaStraddlePosition | None = None
    portfolio: CrossSectionalPortfolio | None = None


def _select(candidate: HestonSubjectCandidate) -> HestonPairSelection | UnknownReason:
    return select_heston_pair(
        candidate.contracts,
        expiration=candidate.selected_expiration,
        require_open_interest=True,
    )


def materialize_heston_family(values: Mapping[str, object]) -> Mapping[str, object]:
    candidates = {
        key: value for key, value in values.items() if isinstance(value, HestonSubjectCandidate)
    }
    output: dict[str, HestonSubjectMaterialization] = {}
    selections: dict[str, HestonPairSelection] = {}
    sort_values: dict[str, Decimal | UnknownReason] = {}
    for subject, candidate in candidates.items():
        if candidate.formation_date_state != "PASS":
            output[subject] = HestonSubjectMaterialization("NO_ACTION", "G_HES_FORMATION_DATE_FAIL")
            continue
        if isinstance(candidate.formation_momentum, UnknownReason):
            output[subject] = HestonSubjectMaterialization(
                "UNKNOWN", candidate.formation_momentum.code
            )
            continue
        selected = _select(candidate)
        if isinstance(selected, UnknownReason):
            output[subject] = HestonSubjectMaterialization(
                "UNKNOWN" if selected.code in UNKNOWN_SELECTION_CODES else "EXCLUDED",
                selected.code,
            )
            continue
        selections[subject] = selected
        sort_values[subject] = candidate.formation_momentum
    parameter_values = tuple(
        heston_parameter(name) for name in ("quantiles", "long_group", "short_group")
    )
    if not all(type(value) is int for value in parameter_values):
        raise TypeError("Heston quantile manifest parameters must be integers")
    quantiles, long_group, short_group = parameter_values
    assert isinstance(quantiles, int)
    assert isinstance(long_group, int)
    assert isinstance(short_group, int)
    assignment = assign_quantiles(sort_values, QuantilePolicy(quantiles))
    if isinstance(assignment, UnknownReason):
        return {
            subject: output.get(subject, HestonSubjectMaterialization("UNKNOWN", assignment.code))
            for subject in values
        }
    groups = dict(assignment.groups)
    positions = {}
    for subject, selection in selections.items():
        call, put = selection.call, selection.put
        call_mid, put_mid = selection.call_mid, selection.put_mid
        group = groups[subject]
        if group not in (long_group, short_group):
            output[subject] = HestonSubjectMaterialization(
                "NO_POSITION", "HESTON_MIDDLE_DECILE", group
            )
            continue
        weights = zero_delta_straddle_weights(call_mid, put_mid, call.delta, put.delta)
        if isinstance(weights, UnknownReason):
            output[subject] = HestonSubjectMaterialization("UNKNOWN", weights.code)
            continue
        direction = OptionLegPosition.LONG if group == long_group else OptionLegPosition.SHORT
        positions[subject] = ZeroDeltaStraddlePosition(
            subject,
            OptionLeg(call, direction, weights.call / call_mid, "zero_delta_call"),
            OptionLeg(put, direction, weights.put / put_mid, "zero_delta_put"),
        )
    portfolio = build_cross_sectional_portfolio(
        as_of=max(candidate.as_of for candidate in candidates.values()),
        evidence_identity="|".join(
            sorted(candidate.evidence_identity for candidate in candidates.values())
        ),
        sort_values=sort_values,
        positions=positions,
        quantile_policy=QuantilePolicy(quantiles),
        included_quantiles=frozenset({long_group, short_group}),
        short_quantiles=frozenset({short_group}),
        weight_policy=PortfolioWeightPolicy.EQUAL,
    )
    if isinstance(portfolio, UnknownReason):
        for subject in positions:
            output[subject] = HestonSubjectMaterialization("UNKNOWN", portfolio.code)
        return output
    for member in portfolio.members:
        output[member.subject] = HestonSubjectMaterialization(
            "PASS", "HESTON_ALL_GATES_PASS", member.quantile, positions[member.subject], portfolio
        )
    return {
        subject: output.get(
            subject, HestonSubjectMaterialization("UNKNOWN", "MISSING_CANONICAL_FACT")
        )
        for subject in values
    }
