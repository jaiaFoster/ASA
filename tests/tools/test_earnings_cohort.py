from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tools.options_truth.earnings_cohort import (
    capture_cohort,
    classify_terminal,
    select_cohort,
)

NOW = datetime(2026, 9, 23, 18, tzinfo=UTC)
SHA = "a" * 40


def _row(symbol: str, earnings_date: str | None) -> dict[str, object]:
    return {
        "symbol": symbol,
        "observation_id": f"obs-{symbol}",
        "canonical_facts": ({} if earnings_date is None else {"earnings_date": earnings_date}),
        "named_derived_facts": {},
    }


def _funnel(terminal: str, reason: str) -> dict[str, object]:
    return {
        "gate_outcomes": [],
        "evaluation_state": "missing_data" if terminal == "evidence_unavailable" else "pass",
        "signal_verdict": None,
        "acquisition": [],
        "structure_status": None,
        "constructibility_reason": None,
        "terminal_state": terminal,
        "terminal_reason": reason,
    }


def test_cohort_prefers_nearest_events_then_fills_with_missing_event_cases() -> None:
    rows = [
        _row("FAR", "2026-10-20"),
        _row("NEAR", "2026-09-24"),
        _row("PAST", "2026-09-20"),
        _row("UNKNOWN", None),
    ]

    selected = select_cohort(rows, as_of=NOW.date(), recent_days=7, future_days=21, limit=3)

    assert [row["symbol"] for row in selected] == ["NEAR", "PAST", "UNKNOWN"]


@pytest.mark.parametrize(
    ("row", "funnel", "expected"),
    (
        (
            _row("A", "2026-09-24"),
            _funnel("evidence_unavailable", "no_valid_expiration_pair"),
            "legitimate_temporal_or_policy_absence",
        ),
        (
            _row("A", "2026-09-24"),
            _funnel("evidence_unavailable", "provider_unavailable"),
            "provider_entitlement_or_coverage",
        ),
        (
            _row("A", None),
            _funnel("evidence_unavailable", "no_data"),
            "genuinely_unknown_or_unannounced_event",
        ),
        (
            _row("A", "2026-09-24"),
            _funnel("strategy_rejected", "liquidity_gate_failed"),
            "true_strategy_rejection",
        ),
        (
            _row("A", "2026-09-24"),
            _funnel("structure_unavailable", "no_common_strike"),
            "structure_or_market_unavailability",
        ),
        (
            _row("A", "2026-09-24"),
            _funnel("structure_unresolved", "subject_preparation_failed"),
            "asa_defect",
        ),
    ),
)
def test_terminal_classification_is_closed_and_typed(
    row: dict[str, object], funnel: dict[str, object], expected: str
) -> None:
    assert classify_terminal(row, funnel) == expected


def test_capture_pins_sha_pages_all_rows_and_emits_checksum() -> None:
    paths: list[str] = []

    def fetch(path: str) -> dict[str, object]:
        paths.append(path)
        if path == "/api/v1/version":
            return {"release_sha": SHA}
        if path.startswith("/api/v1/screening?"):
            return {"results": [_row("AAPL", "2026-09-24")], "total": 1}
        return _funnel("strategy_rejected", "liquidity_gate_failed")

    artifact = capture_cohort(fetch, production_sha=SHA, captured_at=NOW, limit=1)

    assert artifact["production_sha"] == SHA
    assert artifact["cohort_size"] == 1
    assert len(str(artifact["cohort_checksum"])) == 64
    assert artifact["classification_counts"] == {"true_strategy_rejection": 1}
    assert paths[-1] == "/api/v1/screening/earnings_calendar/AAPL/option-funnel"


def test_capture_refuses_wrong_deployment() -> None:
    with pytest.raises(RuntimeError, match="deployed SHA mismatch"):
        capture_cohort(
            lambda _path: {"release_sha": "wrong"},
            production_sha=SHA,
            captured_at=NOW,
        )
