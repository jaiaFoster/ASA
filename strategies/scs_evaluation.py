"""Frozen Santa-Clara/Saretto entry selection and quote filters."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain import OptionChain, OptionContract, OptionType, SettlementStyle, UnknownReason
from strategies.tristate_components import PASS, UNKNOWN

NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class SCSDecision:
    verdict: str
    reason: str
    selected_call: OptionContract | None = None
    selected_put: OptionContract | None = None


def _mid(contract: OptionContract) -> Decimal | None:
    if contract.bid is None or contract.ask is None:
        return None
    return (contract.bid + contract.ask) / Decimal(2)


def _quote_filter(
    contract: OptionContract,
    *,
    spot: Decimal,
    rate: Decimal,
    dividend_yield: Decimal,
    as_of: date,
) -> bool | UnknownReason:
    if (
        contract.bid is None
        or contract.ask is None
        or contract.implied_volatility is None
        or contract.bid <= 0
        or contract.ask < contract.bid
    ):
        return UnknownReason("G_SCS_QUOTE_FILTERS_UNKNOWN")
    mid = _mid(contract)
    assert mid is not None
    tick = Decimal("0.05") if mid < 3 else Decimal("0.10")
    if contract.ask - contract.bid < tick:
        return False
    if not Decimal("0.01") <= contract.implied_volatility <= Decimal("1.00"):
        return False
    tau = Decimal((contract.expiration - as_of).days) / Decimal(365)
    discounted_spot = spot * (-tau * dividend_yield).exp()
    discounted_strike = contract.strike * (-tau * rate).exp()
    if contract.option_type is OptionType.CALL:
        lower, upper = discounted_spot - discounted_strike, discounted_spot
    else:
        lower, upper = discounted_strike - discounted_spot, discounted_strike
    return max(Decimal(0), lower) < mid < upper


def evaluate_scs(
    *,
    decision_date: date,
    entry_date_state: str,
    selected_expiration: date | UnknownReason,
    spot: Decimal | None,
    chain: OptionChain | None,
    rate: Decimal | None,
    dividend_yield: Decimal | None,
) -> SCSDecision:
    if entry_date_state == "FAIL":
        return SCSDecision(NO_ACTION, "G_SCS_ENTRY_DATE_FAIL")
    if entry_date_state != PASS:
        return SCSDecision(UNKNOWN, "G_SCS_ENTRY_DATE_UNKNOWN")
    if isinstance(selected_expiration, UnknownReason):
        return SCSDecision(UNKNOWN, "G_SCS_EXPIRY_UNIQUE_UNKNOWN")
    if spot is None or chain is None:
        return SCSDecision(UNKNOWN, "G_SCS_STRIKE_UNIQUE_UNKNOWN")
    paired = tuple(
        sorted(
            {
                contract.strike
                for contract in chain.contracts
                if contract.expiration == selected_expiration
                and contract.root == "SPX"
                and contract.settlement_style is SettlementStyle.AM
                and chain.find(
                    expiration=selected_expiration,
                    strike=contract.strike,
                    option_type=OptionType.CALL,
                )
                and chain.find(
                    expiration=selected_expiration,
                    strike=contract.strike,
                    option_type=OptionType.PUT,
                )
            }
        )
    )
    if not paired:
        return SCSDecision(UNKNOWN, "G_SCS_STRIKE_UNIQUE_UNKNOWN")
    distances = {strike: abs(strike - spot) for strike in paired}
    minimum = min(distances.values())
    strikes = tuple(strike for strike in paired if distances[strike] == minimum)
    if len(strikes) != 1:
        return SCSDecision(UNKNOWN, "AMBIGUOUS_SELECTION")
    strike = strikes[0]
    call = chain.find(
        expiration=selected_expiration, strike=strike, option_type=OptionType.CALL
    )[0]
    put = chain.find(
        expiration=selected_expiration, strike=strike, option_type=OptionType.PUT
    )[0]
    if rate is None or dividend_yield is None:
        return SCSDecision(UNKNOWN, "G_SCS_QUOTE_FILTERS_UNKNOWN", call, put)
    filtered = tuple(
        _quote_filter(
            item,
            spot=spot,
            rate=rate,
            dividend_yield=dividend_yield,
            as_of=decision_date,
        )
        for item in (call, put)
    )
    if any(isinstance(item, UnknownReason) for item in filtered) or not all(filtered):
        return SCSDecision(UNKNOWN, "G_SCS_QUOTE_FILTERS_UNKNOWN", call, put)
    return SCSDecision(PASS, "SCS_ALL_GATES_PASS", call, put)
