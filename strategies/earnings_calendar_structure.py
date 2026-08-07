"""Earnings Calendar's own pure structural selection (SPRINT-014
S14-PR-05A, Architect checkpoint: ninth review -- the generic read-only
knowledge composition increment).

Split out of what was strategies/earnings_calendar_evaluation.py's own
monolithic evaluate_earnings_calendar(): owns ATM strike/contract
selection -- strategy policy, per ADR-010's "strategies own ... structure
selection" -- and nothing else. Computes no realized volatility, IV
spread, richness, score, or verdict (Architect checkpoint item 2): those
now live downstream, in strategies/earnings_calendar_knowledge_binding.py
(the analytics-materializing integration binding) and
strategies/earnings_calendar_evaluation.py (the now-read-only evaluator),
never here.

Returns EarningsCalendarStructuralSelection -- the structural domain
values (event, chain, cycles, the selected front/back contracts' own
stable identities and implied volatilities) plus the exact demand
identities a caller needs so a later typed UnknownReason stays traceable
to resolved evidence -- or a typed UnknownReason itself for the three
genuine, expected structural data gaps this step alone can determine:
missing spot price, no CALL contracts at a selected expiration, or a
missing implied volatility on the selected ATM contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.atm_selection import select_atm_strike
from domain import (
    EarningsEvent,
    ExpirationCycle,
    OptionChain,
    OptionType,
    Quote,
    UnknownReason,
)


@dataclass(frozen=True, slots=True)
class EarningsCalendarStructuralSelection:
    """Earnings Calendar's own selected structural evidence -- never a
    computed richness/volatility/score.
    """

    spot_price: Decimal
    event: EarningsEvent
    chain: OptionChain
    front_cycle: ExpirationCycle
    back_cycle: ExpirationCycle
    as_of: date
    target_strike: Decimal
    front_contract_identity: str
    back_contract_identity: str
    front_implied_volatility: Decimal
    back_implied_volatility: Decimal
    bars_closes: tuple[Decimal, ...]
    bars_observation_id: str
    quote_demand_id: str
    historical_bars_demand_id: str
    front_chain_demand_id: str
    back_chain_demand_id: str


def select_earnings_calendar_structure(
    *,
    quote: Quote,
    event: EarningsEvent,
    chain: OptionChain,
    bars_closes: tuple[Decimal, ...],
    bars_observation_id: str,
    front_expiration: date,
    back_expiration: date,
    front_cycle: ExpirationCycle,
    back_cycle: ExpirationCycle,
    as_of: date,
    quote_demand_id: str,
    historical_bars_demand_id: str,
    front_chain_demand_id: str,
    back_chain_demand_id: str,
) -> EarningsCalendarStructuralSelection | UnknownReason:
    """Select the exact ATM front/back contracts this cycle's structure
    is built from. Returns a typed UnknownReason (never raises) for each
    genuine, expected structural data gap, carrying the exact demand_id(s)
    it traces back to (Architect checkpoint, seventh review, item 3,
    preserved here): missing spot price, no CALL contracts at a selected
    expiration (select_atm_strike's own empty-strike-set ValueError is
    never let through raw), or a missing implied volatility on the
    selected ATM contract. Historical-bars sufficiency is deliberately
    not checked here -- that gate belongs beside the realized-volatility
    computation itself, in the knowledge binding, not in structural
    selection (item 2: this step computes no volatility).
    """
    if quote.last is None:
        return UnknownReason("missing_spot_price", demand_ids=(quote_demand_id,))
    spot_price = quote.last

    front_strikes = tuple(
        item.strike
        for item in chain.find(expiration=front_expiration, option_type=OptionType.CALL)
    )
    back_strikes = tuple(
        item.strike
        for item in chain.find(expiration=back_expiration, option_type=OptionType.CALL)
    )
    if not front_strikes or not back_strikes:
        no_calls_demand_ids = tuple(
            demand_id
            for empty, demand_id in (
                (not front_strikes, front_chain_demand_id),
                (not back_strikes, back_chain_demand_id),
            )
            if empty
        )
        return UnknownReason(
            "no_call_contracts_at_selected_expiration", demand_ids=no_calls_demand_ids
        )
    front_strike = select_atm_strike(front_strikes, spot_price)
    back_strike = select_atm_strike(back_strikes, spot_price)
    (front_contract,) = chain.find(
        expiration=front_expiration, strike=front_strike, option_type=OptionType.CALL
    )
    (back_contract,) = chain.find(
        expiration=back_expiration, strike=back_strike, option_type=OptionType.CALL
    )
    if front_contract.implied_volatility is None or back_contract.implied_volatility is None:
        missing_iv_demand_ids = tuple(
            demand_id
            for missing, demand_id in (
                (front_contract.implied_volatility is None, front_chain_demand_id),
                (back_contract.implied_volatility is None, back_chain_demand_id),
            )
            if missing
        )
        return UnknownReason("missing_implied_volatility", demand_ids=missing_iv_demand_ids)

    return EarningsCalendarStructuralSelection(
        spot_price=spot_price,
        event=event,
        chain=chain,
        front_cycle=front_cycle,
        back_cycle=back_cycle,
        as_of=as_of,
        target_strike=front_strike,
        front_contract_identity=front_contract.identity,
        back_contract_identity=back_contract.identity,
        front_implied_volatility=front_contract.implied_volatility,
        back_implied_volatility=back_contract.implied_volatility,
        bars_closes=bars_closes,
        bars_observation_id=bars_observation_id,
        quote_demand_id=quote_demand_id,
        historical_bars_demand_id=historical_bars_demand_id,
        front_chain_demand_id=front_chain_demand_id,
        back_chain_demand_id=back_chain_demand_id,
    )
