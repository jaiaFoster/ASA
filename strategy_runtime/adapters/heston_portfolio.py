"""Heston binding onto generic P03/P12 runtime structures."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from analytics.option_facts import option_mid
from analytics.option_returns import zero_delta_straddle_weights
from analytics.quantile_assignment import QuantilePolicy, assign_quantiles
from domain import OptionContract, OptionLeg, OptionLegPosition, OptionType, UnknownReason
from strategies.heston_manifest import heston_parameter
from strategies.heston_portfolio import HestonSubjectCandidate
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


def _select(
    candidate: HestonSubjectCandidate,
) -> tuple[OptionContract, OptionContract, Decimal, Decimal] | UnknownReason:
    lower = Decimal(str(heston_parameter("minimum_call_delta")))
    upper = Decimal(str(heston_parameter("maximum_call_delta")))
    maximum_spread = Decimal(str(heston_parameter("maximum_leg_relative_spread")))
    by_key: dict[tuple[object, Decimal], dict[OptionType, OptionContract]] = {}
    for contract in candidate.contracts:
        if contract.expiration != candidate.selected_expiration:
            continue
        by_key.setdefault((contract.expiration, contract.strike), {})[contract.option_type] = (
            contract
        )
    eligible = []
    incomplete_open_interest = False
    for sides in by_key.values():
        call = sides.get(OptionType.CALL)
        put = sides.get(OptionType.PUT)
        if call is None or put is None or call.delta is None or not lower <= call.delta <= upper:
            continue
        if any(value is None or value <= 0 for value in (call.open_interest, put.open_interest)):
            incomplete_open_interest = incomplete_open_interest or (
                call.open_interest is None or put.open_interest is None
            )
            continue
        eligible.append((abs(call.delta - Decimal("0.5")), call, put))
    if not eligible:
        return UnknownReason(
            "G_HES_LOWCOST_PAIR_UNKNOWN"
            if incomplete_open_interest
            else "G_HES_LOWCOST_PAIR_FAIL"
        )
    minimum = min(item[0] for item in eligible)
    nearest = tuple(item for item in eligible if item[0] == minimum)
    if len(nearest) != 1:
        return UnknownReason("AMBIGUOUS_SELECTION")
    call, put = nearest[0][1:]
    call_mid = option_mid(call.bid, call.ask)
    put_mid = option_mid(put.bid, put.ask)
    if isinstance(call_mid, UnknownReason) or isinstance(put_mid, UnknownReason):
        return UnknownReason("G_HES_LOWCOST_PAIR_UNKNOWN")
    if call.bid is None or call.ask is None or put.bid is None or put.ask is None:
        return UnknownReason("G_HES_LOWCOST_PAIR_UNKNOWN")
    if (call.ask - call.bid) / call_mid > maximum_spread or (
        put.ask - put.bid
    ) / put_mid > maximum_spread:
        return UnknownReason("G_HES_LOWCOST_PAIR_FAIL")
    return call, put, call_mid, put_mid


def materialize_heston_family(values: Mapping[str, object]) -> Mapping[str, object]:
    candidates = {
        key: value for key, value in values.items() if isinstance(value, HestonSubjectCandidate)
    }
    output: dict[str, HestonSubjectMaterialization] = {}
    selections = {}
    sort_values = {}
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
                "UNKNOWN"
                if selected.code in {"AMBIGUOUS_SELECTION", "G_HES_LOWCOST_PAIR_UNKNOWN"}
                else "EXCLUDED",
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
    for subject, (call, put, call_mid, put_mid) in selections.items():
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
