from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from strategy_runtime.forward_outcome import (
    FIRST_EXPIRATION,
    MIDPOINT_MARK_BASIS,
    TERMINAL_INTRINSIC_BASIS,
    FrozenLeg,
    FrozenStructure,
    LegQuote,
    evidence_in_window,
    horizon_schedule,
    modeled_mark,
    outcome_content_identity,
    parse_frozen_structure,
    window_has_passed,
)

# Thursday 2026-09-24 15:00 ET.
ANCHOR = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)


def _spread(expiration: date = date(2026, 10, 23)) -> FrozenStructure:
    return FrozenStructure(
        "proposal-1",
        (
            FrozenLeg("P715", "buy", "put", Decimal("715"), expiration, Decimal(1)),
            FrozenLeg("P755", "sell", "put", Decimal("755"), expiration, Decimal(1)),
        ),
        Decimal("-4.595"),
    )


def test_session_horizons_skip_weekends_and_holidays() -> None:
    schedule = {item.horizon_id: item.due_at for item in horizon_schedule(ANCHOR, None)}

    # d1 = Friday 2026-09-25 close (16:00 ET = 20:00 UTC).
    assert schedule["d1"] == datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    # d5 = Thursday 2026-10-01; d10 = Thursday 2026-10-08.
    assert schedule["d5"] == datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
    assert schedule["d10"] == datetime(2026, 10, 8, 20, 0, tzinfo=UTC)
    assert FIRST_EXPIRATION not in schedule


def test_thanksgiving_week_uses_the_calendar_not_day_counts() -> None:
    # Wednesday 2026-11-25; Thanksgiving 11-26 is closed; 11-27 closes early.
    anchor = datetime(2026, 11, 25, 18, 0, tzinfo=UTC)
    schedule = {item.horizon_id: item.due_at for item in horizon_schedule(anchor, None)}

    assert schedule["d1"] == datetime(2026, 11, 27, 18, 0, tzinfo=UTC)  # 13:00 ET


def test_first_expiration_is_last_and_truncates_later_horizons() -> None:
    schedule = horizon_schedule(ANCHOR, _spread(date(2026, 10, 2)))
    ids = [item.horizon_id for item in schedule]

    assert ids == ["d1", "d5", FIRST_EXPIRATION]
    assert schedule[-1].due_at == datetime(2026, 10, 2, 20, 0, tzinfo=UTC)


def test_schedule_is_a_pure_function_of_frozen_inputs() -> None:
    assert horizon_schedule(ANCHOR, _spread()) == horizon_schedule(ANCHOR, _spread())


def test_eligibility_uses_evidence_time_within_the_versioned_window() -> None:
    due = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)

    assert evidence_in_window(due, due - timedelta(minutes=20))
    assert evidence_in_window(due, due + timedelta(minutes=10))
    assert not evidence_in_window(due, due - timedelta(minutes=21))
    assert not evidence_in_window(due, due + timedelta(minutes=11))
    assert not window_has_passed(due, due + timedelta(minutes=10))
    assert window_has_passed(due, due + timedelta(minutes=11))


def test_credit_spread_mark_and_pnl_signs() -> None:
    quotes = {
        "P715": LegQuote(Decimal("1.00"), Decimal("1.20")),
        "P755": LegQuote(Decimal("3.00"), Decimal("3.40")),
    }

    mark = modeled_mark(_spread(), quotes, horizon_id="d1", underlying_price=Decimal("760"))

    # Position value: +1.10 - 3.20 = -2.10 → -210; entry credit 459.50.
    assert mark.mark_value == Decimal("-210.00")
    assert mark.modeled_pnl == Decimal("249.50")
    assert mark.basis == MIDPOINT_MARK_BASIS
    assert mark.unknown_reasons == ()


def test_missing_or_invalid_leg_quote_makes_the_whole_mark_unknown() -> None:
    quotes = {"P715": LegQuote(Decimal("1.00"), None), "P755": LegQuote(Decimal("3"), Decimal("2"))}

    mark = modeled_mark(_spread(), quotes, horizon_id="d1", underlying_price=Decimal("760"))

    assert mark.mark_value is None and mark.modeled_pnl is None
    assert mark.unknown_reasons == ("P715:missing_bid_ask", "P755:invalid_bid_ask")


def test_first_expiration_values_expiring_legs_at_observed_intrinsic() -> None:
    mark = modeled_mark(_spread(), {}, horizon_id=FIRST_EXPIRATION, underlying_price=Decimal("740"))

    # Long 715P worth 0, short 755P worth 15 → -1500; entry credit 459.50.
    assert mark.mark_value == Decimal("-1500")
    assert mark.modeled_pnl == Decimal("-1040.500")
    assert mark.basis == TERMINAL_INTRINSIC_BASIS
    missing = modeled_mark(_spread(), {}, horizon_id=FIRST_EXPIRATION, underlying_price=None)
    assert missing.mark_value is None


def test_stock_and_legacy_records_have_no_modeled_pnl() -> None:
    assert parse_frozen_structure(None, None) is None
    assert parse_frozen_structure("x", json.dumps({"status": "unavailable"})) is None
    legacy = parse_frozen_structure("x", json.dumps({"exact_legs": []}))
    assert legacy is None
    mark = modeled_mark(None, {}, horizon_id="d1", underlying_price=Decimal("100"))
    assert mark.unknown_reasons == ("no_frozen_structure_entry",)


def test_frozen_proposal_json_round_trips() -> None:
    proposal = {
        "status": "available",
        "legs": [
            {
                "canonical_contract_identity": "P715",
                "buy_or_sell": "buy",
                "call_or_put": "put",
                "strike": "715",
                "expiration": "2026-10-23",
                "quantity": "1",
            }
        ],
        "modeled_entry": {"modeled_net_debit_or_credit": "-4.595"},
    }

    parsed = parse_frozen_structure("proposal-1", json.dumps(proposal))

    assert parsed is not None
    assert parsed.legs[0].strike == Decimal("715")
    assert parsed.modeled_net_debit_or_credit == Decimal("-4.595")


def test_content_identity_is_deterministic() -> None:
    payload = {"horizon_id": "d1", "mark": Decimal("1.00")}
    assert outcome_content_identity(payload) == outcome_content_identity(dict(payload))


def test_model_is_strategy_blind() -> None:
    source = (Path(__file__).parents[2] / "strategy_runtime" / "forward_outcome.py").read_text()
    for strategy_id in (
        "earnings_calendar",
        "forward_factor",
        "skew_momentum",
        "spy_put_credit_spread",
        "B001",
        "B002",
    ):
        assert strategy_id not in source
    assert "universal_screening_state" not in source
