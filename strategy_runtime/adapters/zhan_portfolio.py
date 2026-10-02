"""Zhan binding onto generic P10/P12 runtime structures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.option_facts import option_mid
from analytics.quantile_assignment import QuantilePolicy, assign_quantiles
from domain import (
    OptionContract,
    OptionLeg,
    OptionLegPosition,
    OptionType,
    SecurityType,
    UnknownReason,
)
from strategies.zhan_manifest import zhan_parameter
from strategies.zhan_portfolio import ZhanSubjectCandidate
from strategy_runtime.cross_sectional_portfolio import (
    CrossSectionalPortfolio,
    DeltaHedgedOptionPosition,
    PortfolioWeightPolicy,
    build_cross_sectional_portfolio,
    build_delta_hedged_option_position,
)


@dataclass(frozen=True, slots=True)
class ZhanSubjectMaterialization:
    state: str
    reason: str
    quantile: int | None = None
    position: DeltaHedgedOptionPosition | None = None
    portfolio: CrossSectionalPortfolio | None = None


def _next_month(value: date) -> date:
    return value.replace(year=value.year + (value.month == 12), month=value.month % 12 + 1)


def _eligible_pairs(
    candidate: ZhanSubjectCandidate,
) -> tuple[
    dict[date, tuple[tuple[OptionContract, OptionContract], ...]], UnknownReason | None
]:
    if candidate.spot is None:
        return {}, UnknownReason("G_ZHAN_PRICE_MIN_UNKNOWN")
    threshold = _next_month(candidate.as_of.date())
    by_key: dict[tuple[date, Decimal], dict[OptionType, OptionContract]] = {}
    ambiguous_moneyness = False
    incomplete_market = False
    failed_quote = False
    failed_moneyness = False
    for contract in candidate.contracts:
        mid = option_mid(contract.bid, contract.ask)
        if (
            contract.expiration > threshold
            and (
                isinstance(mid, UnknownReason)
                or contract.volume is None
                or contract.bid is None
                or contract.ask is None
            )
        ):
            incomplete_market = True
        if (
            contract.expiration <= threshold
            or isinstance(mid, UnknownReason)
            or mid < Decimal(str(zhan_parameter("min_mid")))
            or contract.volume is None
            or contract.volume <= 0
            or contract.bid is None
            or contract.ask is None
            or contract.bid <= 0
            or contract.bid >= contract.ask
        ):
            if contract.expiration > threshold and not incomplete_market:
                failed_quote = True
            continue
        ks = contract.strike / candidate.spot
        sk = candidate.spot / contract.strike
        lower = Decimal(str(zhan_parameter("moneyness_min")))
        upper = Decimal(str(zhan_parameter("moneyness_max")))
        ks_inside = lower <= ks <= upper
        sk_inside = lower <= sk <= upper
        if ks_inside != sk_inside:
            ambiguous_moneyness = True
            continue
        if not ks_inside:
            failed_moneyness = True
            continue
        by_key.setdefault((contract.expiration, contract.strike), {})[contract.option_type] = (
            contract
        )
    result: dict[date, list[tuple[OptionContract, OptionContract]]] = {}
    missing_pair = False
    failed_no_arbitrage = False
    for (expiration, _strike), sides in by_key.items():
        if OptionType.CALL not in sides or OptionType.PUT not in sides:
            missing_pair = True
            continue
        call = sides[OptionType.CALL]
        call_mid = option_mid(call.bid, call.ask)
        assert isinstance(call_mid, Decimal)
        assert candidate.risk_free_rate is not None
        years = Decimal((expiration - candidate.as_of.date()).days) / Decimal(365)
        lower_bound = max(
            Decimal(0), candidate.spot - call.strike * (-candidate.risk_free_rate * years).exp()
        )
        if candidate.spot >= call_mid >= lower_bound:
            result.setdefault(expiration, []).append((call, sides[OptionType.PUT]))
        else:
            failed_no_arbitrage = True
    reason = (
        UnknownReason("G_ZHAN_OPTION_QUOTE_UNKNOWN")
        if incomplete_market
        else UnknownReason("G_ZHAN_MONEYNESS_UNKNOWN")
        if ambiguous_moneyness
        else UnknownReason("G_ZHAN_CALL_AND_PUT_FAIL")
        if missing_pair
        else UnknownReason("G_ZHAN_NO_ARBITRAGE_FAIL")
        if failed_no_arbitrage
        else UnknownReason("G_ZHAN_MONEYNESS_FAIL")
        if failed_moneyness
        else UnknownReason("G_ZHAN_OPTION_QUOTE_FAIL")
        if failed_quote
        else None
    )
    return {key: tuple(value) for key, value in result.items()}, reason


def _parameters() -> tuple[int, int, int]:
    values = tuple(zhan_parameter(name) for name in ("quantiles", "long_group", "short_group"))
    if not all(type(value) is int for value in values):
        raise TypeError("Zhan quantile manifest parameters must be integers")
    first, second, third = values
    assert isinstance(first, int) and isinstance(second, int) and isinstance(third, int)
    return first, second, third


def materialize_zhan_family(values: Mapping[str, object]) -> Mapping[str, object]:
    candidates = {
        key: value for key, value in values.items() if isinstance(value, ZhanSubjectCandidate)
    }
    output: dict[str, ZhanSubjectMaterialization] = {}
    shortest: dict[str, tuple[date, tuple[tuple[OptionContract, OptionContract], ...]]] = {}
    for subject, candidate in candidates.items():
        if candidate.formation_date_state != "PASS":
            output[subject] = ZhanSubjectMaterialization(
                "NO_ACTION" if candidate.formation_date_state == "FAIL" else "UNKNOWN",
                "G_ZHAN_FORMATION_DATE_FAIL"
                if candidate.formation_date_state == "FAIL"
                else "G_ZHAN_FORMATION_DATE_UNKNOWN",
            )
            continue
        if candidate.security_type is None:
            output[subject] = ZhanSubjectMaterialization(
                "UNKNOWN", "G_ZHAN_COMMON_STOCK_UNKNOWN"
            )
            continue
        if candidate.spot is None or candidate.negative_log_price is None:
            output[subject] = ZhanSubjectMaterialization("UNKNOWN", "G_ZHAN_PRICE_MIN_UNKNOWN")
            continue
        if candidate.risk_free_rate is None:
            output[subject] = ZhanSubjectMaterialization(
                "UNKNOWN", "G_ZHAN_NO_ARBITRAGE_UNKNOWN"
            )
            continue
        if candidate.shares_outstanding is None:
            output[subject] = ZhanSubjectMaterialization("UNKNOWN", "MISSING_CANONICAL_FACT")
            continue
        assert candidate.spot is not None
        if candidate.security_type is not SecurityType.COMMON_STOCK:
            output[subject] = ZhanSubjectMaterialization(
                "EXCLUDED", "G_ZHAN_COMMON_STOCK_FAIL"
            )
            continue
        if candidate.spot < Decimal(str(zhan_parameter("min_price"))):
            output[subject] = ZhanSubjectMaterialization("EXCLUDED", "G_ZHAN_PRICE_MIN_FAIL")
            continue
        pairs, gate_reason = _eligible_pairs(candidate)
        if not pairs:
            assert gate_reason is not None
            output[subject] = ZhanSubjectMaterialization(
                "UNKNOWN" if gate_reason.code.endswith("_UNKNOWN") else "EXCLUDED",
                gate_reason.code,
            )
            continue
        expiration = min(pairs)
        shortest[subject] = expiration, pairs[expiration]
    counts: dict[date, int] = {}
    for expiration, _pairs in shortest.values():
        counts[expiration] = counts.get(expiration, 0) + 1
    if not counts:
        return {
            subject: output.get(
                subject, ZhanSubjectMaterialization("UNKNOWN", "EMPTY_ELIGIBLE_SET")
            )
            for subject in values
        }
    maximum = max(counts.values())
    modes = tuple(sorted(day for day, count in counts.items() if count == maximum))
    if len(modes) != 1:
        for subject in shortest:
            output[subject] = ZhanSubjectMaterialization("UNKNOWN", "G_ZHAN_MODAL_MATURITY_UNKNOWN")
        return output
    modal = modes[0]
    positions: dict[str, DeltaHedgedOptionPosition] = {}
    sort_values: dict[str, Decimal | UnknownReason] = {}
    weights: dict[str, Decimal] = {}
    selected_calls: dict[str, OptionContract] = {}
    for subject, (expiration, option_pairs) in shortest.items():
        candidate = candidates[subject]
        if expiration != modal:
            output[subject] = ZhanSubjectMaterialization("EXCLUDED", "G_ZHAN_MODAL_MATURITY_FAIL")
            continue
        assert candidate.spot is not None and candidate.shares_outstanding is not None
        nearest_values = [
            (abs(call.strike - candidate.spot), call, put) for call, put in option_pairs
        ]
        minimum = min(item[0] for item in nearest_values)
        nearest = [(call, put) for distance, call, put in nearest_values if distance == minimum]
        if len(nearest) != 1:
            output[subject] = ZhanSubjectMaterialization("UNKNOWN", "AMBIGUOUS_SELECTION")
            continue
        selected_calls[subject] = nearest[0][0]
        assert candidate.negative_log_price is not None
        sort_values[subject] = candidate.negative_log_price
        weights[subject] = candidate.spot * candidate.shares_outstanding
    quantiles, long_group, short_group = _parameters()
    assignment = assign_quantiles(sort_values, QuantilePolicy(quantiles))
    if isinstance(assignment, UnknownReason):
        return {
            subject: output.get(subject, ZhanSubjectMaterialization("UNKNOWN", assignment.code))
            for subject in values
        }
    groups = dict(assignment.groups)
    for subject, call in selected_calls.items():
        group = groups[subject]
        if group not in (long_group, short_group):
            output[subject] = ZhanSubjectMaterialization("NO_POSITION", "ZHN_MIDDLE_DECILE")
            continue
        leg = OptionLeg(
            call,
            OptionLegPosition.LONG if group == long_group else OptionLegPosition.SHORT,
            Decimal(1),
            "delta_neutral_call",
        )
        position = build_delta_hedged_option_position(
            subject, leg, contract_multiplier=Decimal(100)
        )
        if isinstance(position, UnknownReason):
            output[subject] = ZhanSubjectMaterialization("UNKNOWN", position.code)
            continue
        positions[subject] = position
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
        weight_policy=PortfolioWeightPolicy.SOURCE_DEFINED,
        source_weights=weights,
    )
    if isinstance(portfolio, UnknownReason):
        for subject in positions:
            output[subject] = ZhanSubjectMaterialization("UNKNOWN", portfolio.code)
        return output
    for member in portfolio.members:
        output[member.subject] = ZhanSubjectMaterialization(
            "PASS", "ZHAN_ALL_GATES_PASS", member.quantile, positions[member.subject], portfolio
        )
    return {
        subject: output.get(
            subject, ZhanSubjectMaterialization("UNKNOWN", "MISSING_CANONICAL_FACT")
        )
        for subject in values
    }
