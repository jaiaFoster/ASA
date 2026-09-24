from __future__ import annotations

from tests.tools.test_founder_utility import NOW, SHA, _replay_artifacts, _replay_fetch
from tools.options_truth.funnel_census import capture_census


def test_census_traces_every_active_option_row_through_the_real_funnel() -> None:
    fetch, paths = _replay_fetch(*_replay_artifacts())

    artifact = capture_census(fetch, production_sha=SHA, captured_at=NOW)

    assert set(artifact["strategies"]) == {"earnings_calendar", "forward_factor", "skew_momentum"}
    forward = artifact["strategies"]["forward_factor"]
    assert forward["active_total"] == forward["traced"] == 2
    assert forward["terminal_counts"] == {"strategy_rejected": 1, "structure_unavailable": 1}
    assert artifact["unexplained_drop_total"] == 0
    assert artifact["verdict"] == "pass"
    assert not any("refresh" in path or "trade-proposal" in path for path in paths)


def test_qualifying_row_without_readiness_is_an_unexplained_drop() -> None:
    fetch, _ = _replay_fetch(*_replay_artifacts()[:2])

    artifact = capture_census(fetch, production_sha=SHA, captured_at=NOW)

    assert artifact["strategies"]["forward_factor"]["unexplained"] == [
        {"symbol": "MSFT", "reason": "structure_unresolved:execution_readiness_not_available"}
    ]
    assert artifact["verdict"] == "fail_reopen_correction"
