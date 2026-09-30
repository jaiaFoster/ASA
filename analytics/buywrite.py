"""Versioned provider-neutral Cboe buy-write return accounting."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from domain import (
    HistoricalOptionPanel,
    OHLCVBar,
    OHLCVSeries,
    OptionContract,
    OptionTrade,
    OptionTradeTape,
    OptionType,
    UnknownReason,
)

CBOE_BUYWRITE_DAILY_RETURN_ID = "DF-CBOE-BUYWRITE-DAILY-RETURN"
CBOE_BUYWRITE_DAILY_RETURN_VERSION = "1.0.0"
NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class BxmLifecycleFacts:
    """Source-faithful lifecycle inputs; absent evidence stays UNKNOWN."""

    old_strike: Decimal | UnknownReason
    prior_call_close: Decimal | UnknownReason
    current_call_close: Decimal | UnknownReason
    index_vwav: Decimal | UnknownReason
    entry_price: Decimal | UnknownReason


def index_session_closes(
    series: OHLCVSeries | None, session_date: date
) -> tuple[Decimal | UnknownReason, Decimal | UnknownReason]:
    """Prior/current New York session closes from explicit bar end times."""
    missing = UnknownReason("index_session_close_unavailable")
    if series is None:
        return missing, missing
    by_date: dict[date, list[OHLCVBar]] = {}
    for bar in series.bars:
        local = bar.end_at.astimezone(NEW_YORK)
        cutoff = datetime.combine(local.date(), datetime.min.time(), NEW_YORK).replace(hour=16)
        if bar.end_at <= cutoff:
            by_date.setdefault(local.date(), []).append(bar)
    prior_dates = sorted(day for day in by_date if day < session_date)
    current = by_date.get(session_date, [])
    prior = by_date[prior_dates[-1]] if prior_dates else []
    return (
        max(prior, key=lambda item: item.end_at).close if prior else missing,
        max(current, key=lambda item: item.end_at).close if current else missing,
    )


def _eligible_trades(
    tape: OptionTradeTape,
    window_start: datetime,
    window_end: datetime,
    excluded_sale_condition_codes: frozenset[str],
) -> tuple[OptionTrade, ...]:
    return tuple(
        trade
        for trade in tape.trades
        if window_start <= trade.event_time <= window_end
        and not excluded_sale_condition_codes.intersection(trade.sale_condition_codes)
    )


def _last_contract_quote(
    panel: HistoricalOptionPanel,
    contract_identity: str,
    session_date: date,
    cutoff: datetime,
) -> OptionContract | UnknownReason:
    matches = tuple(
        contract
        for snapshot in panel.snapshots
        if snapshot.observed_at.astimezone(NEW_YORK).date() == session_date
        and snapshot.observed_at < cutoff
        for contract in snapshot.contracts
        if contract.identity == contract_identity
        and contract.observed_at.astimezone(NEW_YORK).date() == session_date
        and contract.observed_at < cutoff
    )
    if not matches:
        return UnknownReason("exact_option_quote_before_cutoff_unavailable")
    return max(matches, key=lambda item: item.observed_at)


def option_close_before_new_york_close(
    panel: HistoricalOptionPanel,
    contract_identity: str,
    session_date: date,
) -> Decimal | UnknownReason:
    """Mean of exact contract's last bid/ask observed before 16:00 New York."""
    cutoff = datetime.combine(session_date, datetime.min.time(), NEW_YORK).replace(hour=16)
    quote = _last_contract_quote(panel, contract_identity, session_date, cutoff)
    if isinstance(quote, UnknownReason):
        return quote
    if quote.bid is None or quote.ask is None:
        return UnknownReason("closing_bid_or_ask_unavailable")
    return (quote.bid + quote.ask) / Decimal(2)


def option_entry_price(
    tape: OptionTradeTape | None,
    panel: HistoricalOptionPanel | None,
    contract_identity: str,
    window_start: datetime,
    window_end: datetime,
    *,
    excluded_sale_condition_codes: frozenset[str],
) -> Decimal | UnknownReason:
    """Trade VWAP, or sourced no-trade fallback: last bid before window end."""
    if tape is None or tape.contract_identity != contract_identity:
        return UnknownReason("option_trade_tape_unavailable")
    eligible = _eligible_trades(tape, window_start, window_end, excluded_sale_condition_codes)
    if eligible:
        total = sum((trade.size for trade in eligible), Decimal(0))
        return sum((trade.price * trade.size for trade in eligible), Decimal(0)) / total
    if panel is None:
        return UnknownReason("no_trade_fallback_quote_unavailable")
    quote = _last_contract_quote(
        panel,
        contract_identity,
        window_end.astimezone(NEW_YORK).date(),
        window_end,
    )
    if isinstance(quote, UnknownReason) or quote.bid is None:
        return UnknownReason("no_trade_fallback_quote_unavailable")
    return quote.bid


def index_value_weighted_at_option_trades(
    series: OHLCVSeries | None,
    tape: OptionTradeTape | None,
    window_start: datetime,
    window_end: datetime,
    *,
    excluded_sale_condition_codes: frozenset[str],
) -> Decimal | UnknownReason:
    """Index values at exact option-trade timestamps, with identical size weights.

    When authoritative tape proves no eligible trade, use last index value at or
    before window end. Bars are point observations only at their end timestamp.
    """
    if series is None or tape is None:
        return UnknownReason("aligned_index_observations_unavailable")
    eligible = _eligible_trades(tape, window_start, window_end, excluded_sale_condition_codes)
    by_time = {bar.end_at: bar.close for bar in series.bars}
    if eligible:
        if any(trade.event_time not in by_time for trade in eligible):
            return UnknownReason("aligned_index_observations_unavailable")
        total = sum((trade.size for trade in eligible), Decimal(0))
        weighted = sum(
            (by_time[trade.event_time] * trade.size for trade in eligible),
            Decimal(0),
        )
        return weighted / total
    prior = tuple(bar for bar in series.bars if bar.end_at < window_end)
    if not prior:
        return UnknownReason("index_value_before_window_end_unavailable")
    return max(prior, key=lambda item: item.end_at).close


def resolve_bxm_lifecycle_facts(
    *,
    panel: HistoricalOptionPanel | None,
    series: OHLCVSeries | None,
    tape: OptionTradeTape | None,
    selected_contract_identity: str,
    held_contract_identity: str | None,
    roll_date: date,
    window_start: datetime,
    window_end: datetime,
    excluded_sale_condition_codes: frozenset[str] = frozenset(),
) -> BxmLifecycleFacts:
    """Resolve old/new contract lifecycle inputs from exact sealed evidence."""
    unknown = UnknownReason("historical_option_lifecycle_unavailable")
    if panel is None:
        return BxmLifecycleFacts(
            unknown,
            unknown,
            unknown,
            unknown,
            option_entry_price(
                tape,
                None,
                selected_contract_identity,
                window_start,
                window_end,
                excluded_sale_condition_codes=excluded_sale_condition_codes,
            ),
        )
    prior_dates = sorted(
        {
            snapshot.observed_at.astimezone(NEW_YORK).date()
            for snapshot in panel.snapshots
            if snapshot.observed_at.astimezone(NEW_YORK).date() < roll_date
        }
    )
    if not prior_dates or held_contract_identity is None:
        old_contract: OptionContract | UnknownReason = unknown
        prior_close: Decimal | UnknownReason = unknown
    else:
        prior_date = prior_dates[-1]
        old_candidates = tuple(
            contract
            for snapshot in panel.snapshots
            if snapshot.observed_at.astimezone(NEW_YORK).date() == prior_date
            for contract in snapshot.contracts
            if contract.option_type is OptionType.CALL
            and contract.identity == held_contract_identity
            and contract.expiration == roll_date
        )
        if not old_candidates:
            old_contract = UnknownReason("held_call_identity_not_in_lifecycle_evidence")
            prior_close = old_contract
        else:
            old_contract = max(old_candidates, key=lambda item: item.observed_at)
            prior_close = option_close_before_new_york_close(
                panel, old_contract.identity, prior_date
            )
    current_close = option_close_before_new_york_close(panel, selected_contract_identity, roll_date)
    return BxmLifecycleFacts(
        old_contract.strike if isinstance(old_contract, OptionContract) else old_contract,
        prior_close,
        current_close,
        index_value_weighted_at_option_trades(
            series,
            tape,
            window_start,
            window_end,
            excluded_sale_condition_codes=excluded_sale_condition_codes,
        ),
        option_entry_price(
            tape,
            panel,
            selected_contract_identity,
            window_start,
            window_end,
            excluded_sale_condition_codes=excluded_sale_condition_codes,
        ),
    )


def cboe_buywrite_daily_return(
    *,
    roll_day: bool,
    prior_index_close: Decimal | None,
    prior_call_close: Decimal | None,
    index_close: Decimal | None,
    call_close: Decimal | None,
    dividend_points: Decimal | None,
    old_strike: Decimal | None = None,
    settlement_value: Decimal | None = None,
    index_vwav: Decimal | None = None,
    call_vwap: Decimal | None = None,
) -> Decimal | UnknownReason:
    """Cboe BXM simple daily return, including the three roll-day segments."""
    common = (prior_index_close, prior_call_close, index_close, call_close, dividend_points)
    if any(value is None for value in common):
        return UnknownReason("missing_cboe_buywrite_daily_return_input")
    prior_spot, prior_call, spot, call, dividends = common
    assert prior_spot is not None
    assert prior_call is not None
    assert spot is not None
    assert call is not None
    assert dividends is not None
    prior_net = prior_spot - prior_call
    if min(prior_spot, spot) <= 0 or min(prior_call, call, dividends) < 0 or prior_net <= 0:
        return UnknownReason("invalid_cboe_buywrite_daily_return_input")
    if not roll_day:
        return (spot + dividends - call) / prior_net - Decimal(1)
    roll_inputs = (old_strike, settlement_value, index_vwav, call_vwap)
    if any(value is None for value in roll_inputs):
        return UnknownReason("missing_cboe_buywrite_roll_return_input")
    strike, soq, vwav, premium = roll_inputs
    assert strike is not None
    assert soq is not None
    assert vwav is not None
    assert premium is not None
    if min(strike, soq, vwav, premium) < 0:
        return UnknownReason("invalid_cboe_buywrite_roll_return_input")
    entry_net = vwav - premium
    if soq <= 0 or entry_net <= 0:
        return UnknownReason("invalid_cboe_buywrite_roll_return_input")
    ra = (soq + dividends - max(Decimal(0), soq - strike)) / prior_net - Decimal(1)
    rb = vwav / soq - Decimal(1)
    rc = (spot - call) / entry_net - Decimal(1)
    return (Decimal(1) + ra) * (Decimal(1) + rb) * (Decimal(1) + rc) - Decimal(1)
