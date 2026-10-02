"""Single owner of the Heston low-cost zero-delta straddle pair selection.

Source rule (Heston): at formation, take the monthly-expiration call/put pair
whose call delta is closest to 0.5 within [0.25, 0.75]. If that pair fails the
low-cost (bid-ask spread) screen the subject is excluded and no farther pair is
substituted (RA-XR-03).

ASA implementation assumptions, disclosed and not source rules:

* Call delta is monotone non-increasing in strike within one expiration. A
  strike whose call delta is missing is bounded by its known-delta neighbours.
  If that bound admits a delta at least as close to 0.5 as the best fully
  observed pair, the selection is UNKNOWN rather than silently skipping the
  strike.
* When open interest is required, a pair with unknown open interest whose
  delta distance is no worse than the best eligible pair makes the selection
  UNKNOWN. Resolved non-positive open interest is a failed gate, not UNKNOWN.
* Formation-period returns (lags 2-12) use the same closest-to-0.5 monthly
  pair without the low-cost spread screen or open-interest gate; those screens
  apply only to the pair traded at the current formation date.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.option_facts import option_mid
from domain import OptionContract, OptionType, UnknownReason
from strategies.heston_manifest import heston_parameter

HALF = Decimal("0.5")
PAIR_UNKNOWN = "G_HES_LOWCOST_PAIR_UNKNOWN"
PAIR_FAIL = "G_HES_LOWCOST_PAIR_FAIL"
AMBIGUOUS = "AMBIGUOUS_SELECTION"
UNKNOWN_SELECTION_CODES = frozenset({PAIR_UNKNOWN, AMBIGUOUS})


@dataclass(frozen=True, slots=True)
class HestonPairSelection:
    call: OptionContract
    put: OptionContract
    call_mid: Decimal
    put_mid: Decimal


def _decimal_parameter(name: str) -> Decimal:
    return Decimal(str(heston_parameter(name)))


def _distance_bound(low: Decimal, high: Decimal) -> Decimal:
    """Smallest |delta - 0.5| achievable for a delta in [low, high]."""
    if low <= HALF <= high:
        return Decimal(0)
    return min(abs(low - HALF), abs(high - HALF))


def _positive_open_interest(contract: OptionContract) -> bool | None:
    if contract.open_interest is None:
        return None
    return contract.open_interest > 0


def select_heston_pair(
    contracts: tuple[OptionContract, ...],
    *,
    expiration: date,
    require_open_interest: bool,
    apply_spread_screen: bool = True,
) -> HestonPairSelection | UnknownReason:
    """Select the pair at `expiration`, or a typed reason (UNKNOWN vs. FAIL)."""
    lower = _decimal_parameter("minimum_call_delta")
    upper = _decimal_parameter("maximum_call_delta")
    spread_max = _decimal_parameter("maximum_leg_relative_spread")
    by_strike: dict[Decimal, dict[OptionType, OptionContract]] = {}
    for contract in contracts:
        if contract.expiration == expiration:
            by_strike.setdefault(contract.strike, {})[contract.option_type] = contract
    pairs = sorted(
        (strike, sides[OptionType.CALL], sides[OptionType.PUT])
        for strike, sides in by_strike.items()
        if OptionType.CALL in sides and OptionType.PUT in sides
    )
    known = [(strike, call.delta) for strike, call, _ in pairs if call.delta is not None]
    eligible: list[tuple[Decimal, OptionContract, OptionContract]] = []
    unresolved: list[Decimal] = []
    for strike, call, put in pairs:
        if call.delta is None:
            # Monotone bound from the nearest known-delta neighbours.
            below = [delta for known_strike, delta in known if known_strike < strike]
            above = [delta for known_strike, delta in known if known_strike > strike]
            high = below[-1] if below else Decimal(1)
            low = above[0] if above else Decimal(0)
            if low <= upper and high >= lower:
                unresolved.append(_distance_bound(max(low, lower), min(high, upper)))
            continue
        if not lower <= call.delta <= upper:
            continue
        distance = abs(call.delta - HALF)
        if require_open_interest:
            states = (_positive_open_interest(call), _positive_open_interest(put))
            if False in states:
                continue
            if None in states:
                unresolved.append(distance)
                continue
        eligible.append((distance, call, put))
    if not eligible:
        return UnknownReason(PAIR_UNKNOWN if unresolved else PAIR_FAIL)
    minimum = min(item[0] for item in eligible)
    if any(bound <= minimum for bound in unresolved):
        return UnknownReason(PAIR_UNKNOWN)
    nearest = [item for item in eligible if item[0] == minimum]
    if len(nearest) != 1:
        return UnknownReason(AMBIGUOUS)
    _, call, put = nearest[0]
    call_mid = option_mid(call.bid, call.ask)
    put_mid = option_mid(put.bid, put.ask)
    if (
        isinstance(call_mid, UnknownReason)
        or isinstance(put_mid, UnknownReason)
        or call_mid <= 0
        or put_mid <= 0
        or put.delta is None
    ):
        return UnknownReason(PAIR_UNKNOWN)
    assert call.bid is not None and call.ask is not None
    assert put.bid is not None and put.ask is not None
    if not apply_spread_screen:
        return HestonPairSelection(call, put, call_mid, put_mid)
    if (call.ask - call.bid) / call_mid > spread_max or (put.ask - put.bid) / put_mid > spread_max:
        # RA-XR-03: a failed low-cost screen excludes; no farther pair is substituted.
        return UnknownReason(PAIR_FAIL)
    return HestonPairSelection(call, put, call_mid, put_mid)
