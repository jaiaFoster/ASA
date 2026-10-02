"""SP-08A release classification: closure classes, exceptions, SHA gate."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from tools.options_product.founder_utility import FetchResponse, JsonObject
from tools.strategy_production.release_classification import (
    LIVE_EVALUABLE,
    LIVE_TYPED_DATA_BLOCKER,
    NOT_DUE,
    SELECTED_STRATEGIES,
    UNOBSERVED,
    classify_release,
    classify_row,
)

SHA = "a" * 40
START = datetime(2026, 10, 5, 13, 30, tzinfo=UTC)
END = datetime(2026, 10, 5, 21, 50, tzinfo=UTC)
IN_WINDOW = "2026-10-05T15:00:00Z"


def _row(strategy: str, symbol: str = "SPX", **fields: object) -> JsonObject:
    row: JsonObject = {
        "signal_id": strategy,
        "symbol": symbol,
        "evaluation_state": "no_signal",
        "verdict": "FAIL",
        "metrics": {},
        "blockers": [],
        "updated_at": IN_WINDOW,
    }
    row.update(fields)
    return row


def _fetcher(rows: dict[str, list[JsonObject]], *, sha: str = SHA):
    def fetch(path: str) -> FetchResponse:
        if path == "/api/v1/version":
            return 200, {"release_sha": sha}
        if path == "/api/v1/capabilities":
            return 200, {"signals": [{"signal_id": item} for item in SELECTED_STRATEGIES]}
        query = parse_qs(urlparse(path).query)
        signal_rows = rows.get(query["signal"][0], [])
        offset, limit = int(query["offset"][0]), int(query["limit"][0])
        return 200, {"total": len(signal_rows), "results": signal_rows[offset : offset + limit]}

    return fetch


def test_row_classes_keep_typed_blockers_not_due_and_exceptions_distinct() -> None:
    s = SELECTED_STRATEGIES[0]
    assert classify_row(_row(s, evaluation_state="pass", verdict="PASS")) == LIVE_EVALUABLE
    assert classify_row(_row(s)) == LIVE_EVALUABLE  # due, resolved to a non-pass verdict
    assert classify_row(_row(s, metrics={"decision.state": "NO_ACTION"})) == NOT_DUE
    typed = _row(
        s,
        evaluation_state="missing_data",
        verdict=None,
        blockers=["typed unknown evidence gap: CAPACITY_DEFERRED_INCOMPLETE_COHORT"],
    )
    assert classify_row(typed) == LIVE_TYPED_DATA_BLOCKER
    failed = _row(
        s,
        evaluation_state="missing_data",
        verdict=None,
        blockers=["typed unknown evidence gap: subject_preparation_failed"],
    )
    assert classify_row(failed) == "EXCEPTION"
    # MISSING_DATA without a named reason is never silently a data blocker.
    assert classify_row(_row(s, evaluation_state="missing_data", verdict=None)) == "EXCEPTION"


def test_release_passes_only_when_all_seven_classified_without_exceptions() -> None:
    rows = {strategy: [_row(strategy)] for strategy in SELECTED_STRATEGIES}
    rows["xs_option_zhan_neg_lnprice_dn_call"] = [
        _row(
            "xs_option_zhan_neg_lnprice_dn_call",
            "AAPL",
            evaluation_state="missing_data",
            verdict=None,
            blockers=["typed unknown evidence gap: CAPACITY_DEFERRED_INCOMPLETE_COHORT"],
        )
    ]
    rows["event_vol_gxz_preea_straddle_to_expiry"] = [
        _row("event_vol_gxz_preea_straddle_to_expiry", "AAPL", verdict="NO_ACTION")
    ]
    artifact = classify_release(
        _fetcher(rows), production_sha=SHA, window_start=START, window_end=END, captured_at=END
    )
    assert artifact["verdict"] == "pass", artifact["failures"]
    classes = {name: item["classification"] for name, item in artifact["strategies"].items()}
    assert classes["xs_option_zhan_neg_lnprice_dn_call"] == LIVE_TYPED_DATA_BLOCKER
    assert classes["event_vol_gxz_preea_straddle_to_expiry"] == NOT_DUE
    assert classes["index_putwrite_cboe_put"] == LIVE_EVALUABLE
    assert artifact["strategies"]["xs_option_zhan_neg_lnprice_dn_call"]["blocker_codes"] == {
        "CAPACITY_DEFERRED_INCOMPLETE_COHORT": 1
    }


def test_stale_rows_wrong_sha_and_exceptions_fail_closure() -> None:
    rows = {strategy: [_row(strategy)] for strategy in SELECTED_STRATEGIES}
    rows["index_buywrite_cboe_bxm"] = [
        _row("index_buywrite_cboe_bxm", updated_at="2026-10-02T15:00:00Z")
    ]
    rows["index_putwrite_cboe_puty"].append(
        _row(
            "index_putwrite_cboe_puty",
            "SPX2",
            evaluation_state="missing_data",
            verdict=None,
            blockers=["typed unknown evidence gap: subject_preparation_failed"],
        )
    )
    artifact = classify_release(
        _fetcher(rows, sha="b" * 40),
        production_sha=SHA,
        window_start=START,
        window_end=END,
        captured_at=END,
    )
    assert artifact["verdict"] == "fail"
    assert artifact["strategies"]["index_buywrite_cboe_bxm"]["classification"] == UNOBSERVED
    assert set(artifact["failures"]) == {
        "deployed_sha_mismatch:" + "b" * 40,
        "unobserved:index_buywrite_cboe_bxm",
        "exceptions:index_putwrite_cboe_puty:1",
    }
