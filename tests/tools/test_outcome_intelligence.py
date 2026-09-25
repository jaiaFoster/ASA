from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tools.outcome_intelligence.data_value import build_report, render_markdown, select_sessions
from tools.outcome_intelligence.program_closure import (
    build_closure,
    validate_targets,
)
from tools.outcome_intelligence.program_closure import (
    render_markdown as render_closure,
)
from tools.outcome_intelligence.reason_taxonomy import (
    MARKET,
    PROVIDER,
    UNCLASSIFIED,
    classify,
    reason_code,
)
from tools.outcome_intelligence.session_capture import (
    LEDGER_AVAILABLE,
    LEDGER_NOT_DEPLOYED,
    _outcome_ledger,
)

ROOT = Path(__file__).resolve().parents[2]
ADEQUACY = json.loads(
    (ROOT / "project/research/DATA-RELIABILITY-001/data-adequacy-v1.json").read_text()
)
REGISTRY = json.loads(
    (ROOT / "project/research/OUTCOME-INTELLIGENCE-001/blocked-decisions-v1.json").read_text()
)
INPUTS = json.loads(
    (ROOT / "project/research/OUTCOME-INTELLIGENCE-001/program-closure-inputs-v1.json").read_text()
)


def _capture(
    session_date: str,
    captured_at: str,
    *,
    actionable: int = 1,
    unexplained: int = 0,
    ledger: dict[str, Any] | None = None,
    extra_reason: str | None = None,
) -> dict[str, Any]:
    reasons = {
        "actionable_opportunity:constructible_as_intended": actionable,
        "evidence_unavailable:typed unknown evidence gap: missing_implied_volatility": 2,
        "evidence_unavailable:typed unknown evidence gap: no_valid_expiration_pair": 5,
        "strategy_rejected:verdict:fail": 10,
    }
    if extra_reason:
        reasons[f"evidence_unavailable:typed unknown evidence gap: {extra_reason}"] = 1
    active = sum(reasons.values())
    return {
        "artifact_kind": "program_session_capture",
        "artifact_version": "1.0.0",
        "production_sha": "a" * 40,
        "captured_at": captured_at,
        "session_date": session_date,
        "census": {
            "unexplained_drop_total": unexplained,
            "strategies": {
                "alpha_option": {
                    "active_total": active,
                    "traced": active,
                    "terminal_counts": {
                        "actionable_opportunity": actionable,
                        "evidence_unavailable": active - actionable - 10,
                        "strategy_rejected": 10,
                    },
                    "terminal_reason_counts": reasons,
                    "unexplained": [],
                    "actionable": [
                        {"symbol": f"S{index}", "observed_at": f"{session_date}T19:50:00Z"}
                        for index in range(actionable)
                    ],
                }
            },
        },
        "trade_cards": {
            "signals": {"alpha_option": {"qualifying_verdict_count": actionable + 1}},
            "qualifying_option_results": actionable + 1,
            "outcome_counts": {
                "complete_trade_card": actionable,
                "typed_failure_presentation": 1,
            },
            "observations": [],
        },
        "stocks": {
            "stock_signals": ["beta_stock", "gamma_stock"],
            "defect_count": 0,
            "observations": [
                {
                    "signal_id": "beta_stock",
                    "status": "actionable",
                    "unknown_reasons": [],
                    "evidence_age_seconds": 120,
                },
                {
                    "signal_id": "gamma_stock",
                    "status": "unknown",
                    "unknown_reasons": ["unusable_historical_bars"],
                    "evidence_age_seconds": 120,
                },
            ],
        },
        "outcomes": ledger or {"ledger_status": LEDGER_NOT_DEPLOYED, "candidates": []},
    }


_OBSERVED_LEDGER = {
    "ledger_status": LEDGER_AVAILABLE,
    "candidates": [
        {
            "candidate_id": "c1",
            "strategy_id": "alpha_option",
            "symbol": "SPY",
            "tracked_at": "2026-09-24T19:00:00Z",
            "has_frozen_proposal": True,
            "horizons": [
                {"horizon_id": "d1", "status": "observed", "has_modeled_pnl": True},
                {"horizon_id": "d5", "status": "missed", "has_modeled_pnl": False},
                {"horizon_id": "d10", "status": "pending", "has_modeled_pnl": False},
            ],
        }
    ],
}

# Five consecutive sessions, each captured after its 16:00 ET close.
_DATES = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25"]


def _corpus(**kwargs: Any) -> list[dict[str, Any]]:
    return [_capture(day, f"{day}T21:15:00+00:00", **kwargs) for day in _DATES]


def test_reason_taxonomy_extracts_typed_codes_and_never_guesses() -> None:
    assert reason_code("typed unknown evidence gap: missing_earnings_date") == (
        "missing_earnings_date"
    )
    assert reason_code("earnings_clearance:unknown_unconfirmed") == "earnings_clearance"
    assert reason_code("verdict:fail") == "verdict"
    assert classify("missing_implied_volatility").category == PROVIDER
    assert classify("no_valid_expiration_pair").category == MARKET
    assert classify("never_seen_reason").category == UNCLASSIFIED


def test_sessions_keep_latest_capture_and_reject_intraday_and_non_sessions() -> None:
    sessions = select_sessions(
        [
            _capture("2026-09-24", "2026-09-24T21:00:00+00:00", actionable=1),
            _capture("2026-09-24", "2026-09-24T22:00:00+00:00", actionable=3),
            _capture("2026-09-25", "2026-09-25T15:00:00+00:00"),
            _capture("2026-09-26", "2026-09-26T21:00:00+00:00"),
        ]
    )
    assert [(item.session_date, item.eligible, item.ineligible_reason) for item in sessions] == [
        ("2026-09-24", True, None),
        ("2026-09-25", False, "captured_before_session_close"),
        ("2026-09-26", False, "not_a_market_session"),
    ]
    assert sessions[0].capture["captured_at"] == "2026-09-24T22:00:00+00:00"


def test_data_value_report_refuses_completion_without_sufficient_evidence() -> None:
    report = build_report(_corpus()[:2], ADEQUACY, REGISTRY, repository_root=ROOT)

    assert report["verdict"] == "evidence_insufficient"
    assert report["insufficiency"] == [
        "eligible_sessions 2 < required 5",
        f"forward_outcome_ledger {LEDGER_NOT_DEPLOYED}",
    ]
    assert report["forward_outcomes"] == {"ledger_status": LEDGER_NOT_DEPLOYED, "by_strategy": {}}
    assert "It is not reported as zero" in render_markdown(report)


def test_data_value_report_quantifies_counts_losses_samples_and_gaps() -> None:
    corpus = _corpus()
    corpus[-1]["outcomes"] = _OBSERVED_LEDGER
    report = build_report(corpus, ADEQUACY, REGISTRY, repository_root=ROOT)

    assert report["verdict"] == "complete"
    counts = report["opportunity_counts"]["by_strategy"]
    assert counts["alpha_option"]["actionable_total"] == 5
    assert counts["beta_stock"]["actionable_mean_per_session"] == 1.0
    attribution = report["capability_attribution"]
    assert attribution["provider_capability_totals"] == {
        "historical_bars_v1": 5,
        "option_chain_v1": 10,
    }
    assert attribution["category_totals"][MARKET] == 25
    assert attribution["unclassified"] == []
    samples = report["forward_outcomes"]["by_strategy"]["alpha_option"]
    assert samples["observed_with_modeled_pnl"] == 1
    assert samples["due_horizon_coverage"] == 0.5
    assert samples["meets_sample_guard"] is False
    gaps = {row["required_capability"]: row for row in report["paid_capability_gaps"]}
    options_gap = gaps[
        "complete option expiration, contract, quote, Greek, and implied-volatility evidence"
    ]
    assert options_gap["observed_rows_resolvable"] == {"latest_session": 2, "mean_per_session": 2.0}
    assert "BD-07" in options_gap["blocked_decisions"]
    decisions = {item["id"]: item for item in report["blocked_decisions"]}
    assert decisions["BD-02"]["latest_session_observed_total"] == 1
    assert decisions["BD-01"]["paid_data_could_resolve"] == "no"


def test_data_value_report_is_deterministic_and_input_order_independent() -> None:
    corpus = _corpus()
    first = build_report(corpus, ADEQUACY, REGISTRY, repository_root=ROOT)
    second = build_report(
        list(reversed(copy.deepcopy(corpus))), ADEQUACY, REGISTRY, repository_root=ROOT
    )
    assert first == second
    assert render_markdown(first) == render_markdown(second)


def test_unclassified_reason_blocks_completion_and_is_listed() -> None:
    corpus = _corpus(extra_reason="brand_new_reason")
    corpus[-1]["outcomes"] = _OBSERVED_LEDGER
    report = build_report(corpus, ADEQUACY, REGISTRY, repository_root=ROOT)
    assert report["verdict"] == "evidence_insufficient"
    assert report["insufficiency"] == ["unclassified_reasons brand_new_reason"]


def test_registry_evidence_and_gaps_must_exist() -> None:
    registry = copy.deepcopy(REGISTRY)
    registry["decisions"][0]["evidence_refs"] = ["project/reports/DOES-NOT-EXIST.md"]
    with pytest.raises(ValueError, match="evidence reference"):
        build_report(_corpus(), ADEQUACY, registry, repository_root=ROOT)
    registry = copy.deepcopy(REGISTRY)
    registry["decisions"][0]["unlock_gaps"] = ["invented capability"]
    with pytest.raises(ValueError, match="absent from the adequacy artifact"):
        build_report(_corpus(), ADEQUACY, registry, repository_root=ROOT)


def test_closure_is_pending_until_evidence_exists_and_never_claims_closed() -> None:
    corpus = _corpus()[:1]
    data_value = build_report(corpus, ADEQUACY, REGISTRY, repository_root=ROOT)
    report = build_closure(corpus, data_value, INPUTS, repository_root=ROOT)

    assert report["verdict"] == "observation_pending"
    gates = {item["gate"]: item["state"] for item in report["gates"]}
    assert gates == {
        "prior_sprints_closed": "pass",
        "forward_ledger_deployed": "pending",
        "forward_outcome_observed": "pending",
        "aoy_measured": "pending",
        "zero_unexplained_drops": "pass",
        "presentation_defect_free": "pass",
        "oi07_data_value_complete": "pending",
        "no_open_corrections": "pass",
    }
    assert report["aoy"]["total"]["mean"] == 2.0
    session = report["per_session"][0]
    assert session["aoy_option"] == 1 and session["aoy_stock"] == 1
    assert session["constructible_rate_after_qualifying"] == 0.5
    assert session["median_actionable_evidence_age_at_close_seconds"] == 300.0


def test_closure_ready_carries_the_strategy_library_downgrade() -> None:
    corpus = _corpus()
    corpus[-1]["outcomes"] = _OBSERVED_LEDGER
    data_value = build_report(corpus, ADEQUACY, REGISTRY, repository_root=ROOT)
    report = build_closure(corpus, data_value, INPUTS, repository_root=ROOT)

    assert report["verdict"] == "closure_ready_with_downgrades"
    assert report["unmet_targets"][0]["sprint"] == "STRATEGY-LIBRARY-001"
    rendered = render_closure(report)
    assert "**UNMET (downgraded)**: STRATEGY-LIBRARY-001" in rendered
    assert "This is not a success" in rendered


def test_unexplained_drop_reopens_instead_of_closing() -> None:
    corpus = _corpus(unexplained=1)
    corpus[-1]["outcomes"] = _OBSERVED_LEDGER
    data_value = build_report(corpus, ADEQUACY, REGISTRY, repository_root=ROOT)
    assert build_closure(corpus, data_value, INPUTS, repository_root=ROOT)["verdict"] == (
        "reopen_required"
    )


def test_downgrade_can_never_be_relabelled_as_success() -> None:
    inputs = copy.deepcopy(INPUTS)
    library = next(item for item in inputs["sprints"] if item["sprint"] == "STRATEGY-LIBRARY-001")
    library["targets"][0]["met"] = True
    library["state"] = "closed"
    with pytest.raises(ValueError, match="can never be relabelled"):
        validate_targets(inputs, ROOT)
    library["targets"] = []
    with pytest.raises(ValueError, match="can never be relabelled"):
        validate_targets(inputs, ROOT)


def test_ledger_distinguishes_undeployed_route_from_available_empty_corpus() -> None:
    def undeployed(path: str) -> tuple[int, dict[str, Any]]:
        if path == "/api/v1/portfolio/tracked-candidates":
            return 200, [{"id": "c1"}]  # type: ignore[return-value]
        return 404, {"detail": "Not Found"}

    assert _outcome_ledger(undeployed) == {"ledger_status": LEDGER_NOT_DEPLOYED, "candidates": []}
    assert _outcome_ledger(lambda path: (200, [])) == {  # type: ignore[arg-type, return-value]
        "ledger_status": LEDGER_AVAILABLE,
        "candidates": [],
    }
