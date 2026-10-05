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
CLEAN_CRON = [
    '{"artifact_type": "bounded_run_cohort", "results": '
    '[{"signal_id": "index_putwrite_cboe_put", "error": null}]}'
]


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
        _fetcher(rows),
        production_sha=SHA,
        window_start=START,
        window_end=END,
        captured_at=END,
        cron_lines=CLEAN_CRON,
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
        cron_lines=CLEAN_CRON,
    )
    assert artifact["verdict"] == "fail"
    assert artifact["strategies"]["index_buywrite_cboe_bxm"]["classification"] == UNOBSERVED
    assert set(artifact["failures"]) == {
        "deployed_sha_mismatch:" + "b" * 40,
        "unobserved:index_buywrite_cboe_bxm",
        "exceptions:index_putwrite_cboe_puty:1",
    }


def test_complete_family_without_rows_is_not_due_only_off_formation() -> None:
    rows = {strategy: [_row(strategy)] for strategy in SELECTED_STRATEGIES}
    for family in (
        "xs_option_zhan_neg_lnprice_dn_call",
        "xs_option_heston_straddle_momentum_lowcost",
    ):
        rows[family] = []
    # 2026-10-05 is neither a month-end nor a monthly-expiration session.
    artifact = classify_release(
        _fetcher(rows),
        production_sha=SHA,
        window_start=START,
        window_end=END,
        captured_at=END,
        cron_lines=CLEAN_CRON,
    )
    assert artifact["verdict"] == "pass", artifact["failures"]
    assert artifact["strategies"]["xs_option_zhan_neg_lnprice_dn_call"]["classification"] == NOT_DUE
    # On the Heston formation date the absence of rows is UNOBSERVED, never NOT_DUE.
    formation = classify_release(
        _fetcher(rows),
        production_sha=SHA,
        window_start=datetime(2026, 10, 16, 13, 30, tzinfo=UTC),
        window_end=datetime(2026, 10, 16, 21, 50, tzinfo=UTC),
        captured_at=END,
        cron_lines=CLEAN_CRON,
    )
    heston = formation["strategies"]["xs_option_heston_straddle_momentum_lowcost"]
    assert heston["classification"] == UNOBSERVED
    assert "unobserved:xs_option_heston_straddle_momentum_lowcost" in formation["failures"]


def test_knowledge_construction_failure_is_an_exception_not_a_data_blocker() -> None:
    row = _row(
        SELECTED_STRATEGIES[0],
        evaluation_state="missing_data",
        verdict=None,
        blockers=[
            "typed unknown evidence gap: strategy_knowledge_construction_failed "
            "(failure_class=unexpected_runtime_exception;exception_type=KeyError)"
        ],
    )
    assert classify_row(row) == "EXCEPTION"


def test_window_ending_before_the_formation_close_is_never_not_due() -> None:
    rows = {
        strategy: [_row(strategy, updated_at="2026-10-30T15:00:00Z")]
        for strategy in SELECTED_STRATEGIES
    }
    rows["xs_option_zhan_neg_lnprice_dn_call"] = []
    artifact = classify_release(
        _fetcher(rows),
        production_sha=SHA,
        window_start=datetime(2026, 10, 30, 13, 30, tzinfo=UTC),
        window_end=datetime(2026, 10, 30, 20, 0, tzinfo=UTC),  # at the EDT close
        captured_at=END,
        cron_lines=CLEAN_CRON,
    )
    zhan = artifact["strategies"]["xs_option_zhan_neg_lnprice_dn_call"]
    assert zhan["classification"] == UNOBSERVED
    assert artifact["verdict"] == "fail"


def test_missing_or_failing_cron_evidence_fails_closure() -> None:
    rows = {strategy: [_row(strategy)] for strategy in SELECTED_STRATEGIES}
    for family in (
        "xs_option_zhan_neg_lnprice_dn_call",
        "xs_option_heston_straddle_momentum_lowcost",
    ):
        rows[family] = []
    kwargs = dict(production_sha=SHA, window_start=START, window_end=END, captured_at=END)
    assert classify_release(_fetcher(rows), **kwargs)["failures"] == ["cron_evidence_missing"]
    failing = [
        'INFO {"artifact_type": "bounded_run_cohort", "results": ['
        '{"signal_id": "index_buywrite_cboe_bxm", "error": "boom"}, '
        '{"signal_id": "forward_factor", "error": "ignored: not selected"}]}',
        "WARNING fixed_subject_option_refresh_failed failure_class=RuntimeError",
    ]
    artifact = classify_release(_fetcher(rows), cron_lines=failing, **kwargs)
    assert artifact["failures"] == [
        "cron_pair_failures:index_buywrite_cboe_bxm:1",
        "cron_refresh_failures:1",
    ]
    # SP-08A 2026-10-05: a clean cohort artifact does not hide an exception
    # the scheduler caught and logged (execution_readiness_projection_failed).
    swallowed = [
        'INFO {"artifact_type": "bounded_run_cohort", "results": []}',
        "ERROR execution_readiness_projection_failed",
        "ERROR Traceback (most recent call last):",
    ]
    artifact = classify_release(_fetcher(rows), cron_lines=swallowed, **kwargs)
    assert artifact["failures"] == ["cron_tracebacks:1"]
    assert artifact["cron_evidence"]["traceback_lines"] == 1
