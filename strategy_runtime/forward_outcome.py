"""Pure forward-outcome model for tracked proposals (OUTCOME-INTELLIGENCE OI-02).

Implements the Architect-approved amendments
(project/reports/OUTCOME-INTELLIGENCE-001-OI-02-04-ARCHITECT-DECISION.md):

- horizons are generic runtime policy ``oi-horizons-v1`` computed only from
  frozen data and the session calendar -- never from strategy identity;
- eligibility is judged by provider evidence time inside a versioned window
  around the due close, never by wall clock; nothing is backfilled;
- the mark is the midpoint of the exact frozen legs, all-or-UNKNOWN, labelled
  as a model and never as a fill; legs expiring at ``first_expiration`` are
  valued at intrinsic from the observed underlying.

No I/O, no acquisition, no persistence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from domain.values import require_tz_aware
from market_data.session_calendar import NEW_YORK, UsEquitySessionCalendar

HORIZON_POLICY_VERSION = "oi-horizons-v1"
MARK_MODEL_VERSION = "oi-midpoint-mark-v1"
MIDPOINT_MARK_BASIS = "modeled_midpoint_mark_not_fill"
TERMINAL_INTRINSIC_BASIS = "terminal_intrinsic_from_observed_underlying"
WINDOW_BEFORE_CLOSE = timedelta(minutes=20)
WINDOW_AFTER_CLOSE = timedelta(minutes=10)
SESSION_HORIZONS = (("d1", 1), ("d5", 5), ("d10", 10))
FIRST_EXPIRATION = "first_expiration"
_MAX_SESSION_SCAN_DAYS = 40


class OutcomeStatus(StrEnum):
    OBSERVED = "observed"
    MISSED = "missed"
    NOT_OBSERVABLE_BEFORE_TRACKING = "not_observable_before_tracking"


@dataclass(frozen=True, slots=True)
class FrozenLeg:
    canonical_contract_identity: str
    buy_or_sell: str
    call_or_put: str
    strike: Decimal
    expiration: date
    quantity: Decimal

    @property
    def sign(self) -> Decimal:
        return Decimal(1) if self.buy_or_sell == "buy" else Decimal(-1)


@dataclass(frozen=True, slots=True)
class FrozenStructure:
    """The exact frozen structure and entry of one tracked proposal."""

    proposal_identity: str
    legs: tuple[FrozenLeg, ...]
    modeled_net_debit_or_credit: Decimal


@dataclass(frozen=True, slots=True)
class HorizonDue:
    horizon_id: str
    due_at: datetime


def parse_frozen_structure(
    proposal_identity: str | None, proposal_json: str | None
) -> FrozenStructure | None:
    """Read only the canonical frozen proposal; legacy/stock records yield None."""
    if proposal_identity is None or proposal_json is None:
        return None
    data = json.loads(proposal_json)
    if not isinstance(data, dict) or data.get("status") != "available":
        return None
    legs_data = data.get("legs")
    entry = data.get("modeled_entry")
    if not isinstance(legs_data, list) or not legs_data or not isinstance(entry, dict):
        return None
    legs = tuple(
        FrozenLeg(
            str(item["canonical_contract_identity"]),
            str(item["buy_or_sell"]),
            str(item["call_or_put"]),
            Decimal(str(item["strike"])),
            date.fromisoformat(str(item["expiration"])),
            Decimal(str(item["quantity"])),
        )
        for item in legs_data
    )
    return FrozenStructure(
        proposal_identity, legs, Decimal(str(entry["modeled_net_debit_or_credit"]))
    )


def _sessions_after(
    calendar: UsEquitySessionCalendar, anchor_date: date, count: int
) -> tuple[datetime, ...]:
    closes: list[datetime] = []
    cursor = anchor_date
    for _ in range(_MAX_SESSION_SCAN_DAYS):
        cursor += timedelta(days=1)
        session = calendar.session(cursor)
        if session is not None:
            closes.append(session.closes_at)
            if len(closes) == count:
                return tuple(closes)
    raise ValueError("session calendar scan exceeded its bound")


def _session_close_on_or_before(calendar: UsEquitySessionCalendar, day: date) -> datetime:
    cursor = day
    for _ in range(_MAX_SESSION_SCAN_DAYS):
        session = calendar.session(cursor)
        if session is not None:
            return session.closes_at
        cursor -= timedelta(days=1)
    raise ValueError("session calendar scan exceeded its bound")


def horizon_schedule(
    anchor: datetime,
    structure: FrozenStructure | None,
    *,
    calendar: UsEquitySessionCalendar | None = None,
) -> tuple[HorizonDue, ...]:
    """Pure schedule from the frozen anchor, legs, and calendar (oi-horizons-v1).

    ``dN`` is the close of the Nth session strictly after the anchor's New York
    trading date (``next_session_close`` is ``d1``). ``first_expiration`` is the
    close of the last session on or before the earliest leg expiration, only
    for a frozen option structure, and no horizon is scheduled after it.
    """
    require_tz_aware(anchor, "horizon_schedule", "anchor")
    resolved = calendar or UsEquitySessionCalendar()
    anchor_date = anchor.astimezone(NEW_YORK).date()
    closes = _sessions_after(resolved, anchor_date, SESSION_HORIZONS[-1][1])
    horizons = [HorizonDue(horizon_id, closes[index - 1]) for horizon_id, index in SESSION_HORIZONS]
    if structure is not None:
        expiry_close = _session_close_on_or_before(
            resolved, min(leg.expiration for leg in structure.legs)
        )
        if expiry_close > anchor:
            horizons = [item for item in horizons if item.due_at < expiry_close]
            horizons.append(HorizonDue(FIRST_EXPIRATION, expiry_close))
    return tuple(sorted(horizons, key=lambda item: item.due_at))


def evidence_in_window(due_at: datetime, evidence_observed_at: datetime) -> bool:
    """Eligibility is judged by provider evidence time, never wall clock."""
    return due_at - WINDOW_BEFORE_CLOSE <= evidence_observed_at <= due_at + WINDOW_AFTER_CLOSE


def window_has_passed(due_at: datetime, now: datetime) -> bool:
    return now > due_at + WINDOW_AFTER_CLOSE


@dataclass(frozen=True, slots=True)
class LegQuote:
    bid: Decimal | None
    ask: Decimal | None


@dataclass(frozen=True, slots=True)
class ModeledMark:
    """All-or-UNKNOWN modeled mark; never an executed fill."""

    mark_value: Decimal | None
    modeled_pnl: Decimal | None
    basis: str
    unknown_reasons: tuple[str, ...]
    model_version: str = MARK_MODEL_VERSION


def _intrinsic(leg: FrozenLeg, underlying: Decimal) -> Decimal:
    if leg.call_or_put == "call":
        return max(Decimal(0), underlying - leg.strike)
    return max(Decimal(0), leg.strike - underlying)


def modeled_mark(
    structure: FrozenStructure | None,
    quotes: Mapping[str, LegQuote],
    *,
    horizon_id: str,
    underlying_price: Decimal | None,
    contract_multiplier: Decimal = Decimal("100"),
) -> ModeledMark:
    """Σ side × qty × value × multiplier over the exact frozen legs."""
    if structure is None:
        return ModeledMark(None, None, MIDPOINT_MARK_BASIS, ("no_frozen_structure_entry",))
    expiring = (
        min(leg.expiration for leg in structure.legs) if horizon_id == FIRST_EXPIRATION else None
    )
    reasons: list[str] = []
    total = Decimal(0)
    for leg in structure.legs:
        if expiring is not None and leg.expiration == expiring:
            if underlying_price is None:
                reasons.append(f"{leg.canonical_contract_identity}:missing_underlying_price")
                continue
            value = _intrinsic(leg, underlying_price)
        else:
            quote = quotes.get(leg.canonical_contract_identity)
            if quote is None or quote.bid is None or quote.ask is None:
                reasons.append(f"{leg.canonical_contract_identity}:missing_bid_ask")
                continue
            if not Decimal(0) <= quote.bid <= quote.ask:
                reasons.append(f"{leg.canonical_contract_identity}:invalid_bid_ask")
                continue
            value = (quote.bid + quote.ask) / Decimal(2)
        total += leg.sign * leg.quantity * value
    basis = TERMINAL_INTRINSIC_BASIS if expiring is not None else MIDPOINT_MARK_BASIS
    if reasons:
        return ModeledMark(None, None, basis, tuple(reasons))
    mark = total * contract_multiplier
    return ModeledMark(
        mark,
        mark - structure.modeled_net_debit_or_credit * contract_multiplier,
        basis,
        (),
    )


def outcome_content_identity(payload: Mapping[str, object]) -> str:
    """sha256 over canonical JSON; identical re-collection is idempotent."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
