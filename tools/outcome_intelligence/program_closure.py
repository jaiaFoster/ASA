"""Program closure machinery for ASA-OPTIONS-TO-OUTCOMES-2026Q4.

This computes AOY (Actionable Opportunity Yield) and the supporting coverage
metrics from accumulated session captures. It evaluates evidence gates and
renders the closure report that the program prompt requires.

Final closure is a matter of inserting and validating evidence: re-run this
over the capture corpus and the OI-07 report. The tool never declares the
program closed. Its best verdict is ``closure_ready``, and it withholds even
that until every evidence gate passes. Any target recorded as unmet is carried
as UNMET (downgraded) in every rendering, and it can never be relabelled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from market_data.session_calendar import UsEquitySessionCalendar
from tools.outcome_intelligence.data_value import (
    DEFAULT_MINIMUM_ELIGIBLE_SESSIONS,
    Session,
    select_sessions,
    session_losses,
    session_opportunities,
)
from tools.outcome_intelligence.reason_taxonomy import PROVIDER
from tools.outcome_intelligence.session_capture import LEDGER_AVAILABLE

JsonObject = dict[str, Any]

REPORT_VERSION = "1.0.0"
PASS, PENDING, FAIL = "pass", "pending", "fail"
_CLOSED_STATES = frozenset({"closed", "closed_with_downgrade"})
_THIS_SPRINT = "OUTCOME-INTELLIGENCE-001"


def _ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def session_metrics(session: Session) -> JsonObject:
    capture = session.capture
    opportunities = session_opportunities(capture)
    options = {k: v for k, v in opportunities.items() if v["asset_class"] == "option"}
    stocks = {k: v for k, v in opportunities.items() if v["asset_class"] == "stock"}
    census = capture["census"]
    option_active = sum(item["active_total"] for item in census["strategies"].values())
    traced = sum(item["traced"] for item in census["strategies"].values())
    evidence_unavailable = sum(
        item["terminal_counts"].get("evidence_unavailable", 0)
        for item in census["strategies"].values()
    )
    stock_unknown = sum(item["status"] == "unknown" for item in capture["stocks"]["observations"])
    stock_active = len(capture["stocks"]["observations"])
    provider_by_capability: dict[str, int] = {}
    for row in session_losses(capture):
        if row["category"] == PROVIDER:
            provider_by_capability[row["capability"]] = (
                provider_by_capability.get(row["capability"], 0) + row["count"]
            )
    # Evidence age is measured at the session close, not at capture time, so
    # sessions captured at different hours stay comparable.
    captured_at = datetime.fromisoformat(capture["captured_at"])
    market = UsEquitySessionCalendar().session(date.fromisoformat(session.session_date))
    if market is None:
        raise ValueError(f"{session.session_date} is not a market session")
    observed_times = [
        datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
        for strategy in census["strategies"].values()
        for item in strategy.get("actionable", [])
    ] + [
        captured_at - timedelta(seconds=float(item["evidence_age_seconds"]))
        for item in capture["stocks"]["observations"]
        if item["status"] == "actionable" and item.get("evidence_age_seconds") is not None
    ]
    ages = [max(0.0, (market.closes_at - item).total_seconds()) for item in observed_times]
    cards = capture["trade_cards"]
    option_actionable = sum(item["actionable"] for item in options.values())
    option_qualifying = sum(item["qualifying"] for item in options.values())
    stock_actionable = sum(item["actionable"] for item in stocks.values())
    return {
        "session_date": session.session_date,
        "production_sha": capture["production_sha"],
        "aoy": option_actionable + stock_actionable,
        "aoy_option": option_actionable,
        "aoy_stock": stock_actionable,
        "evaluation_coverage": _ratio(traced, option_active),
        "unexplained_drop_count": census["unexplained_drop_total"],
        "strategy_evaluation_completion_rate": _ratio(
            option_active + stock_active - evidence_unavailable - stock_unknown,
            option_active + stock_active,
        ),
        "constructible_rate_after_qualifying": _ratio(option_actionable, option_qualifying),
        "provider_limited_rate_by_capability": {
            key: _ratio(value, option_active + stock_active)
            for key, value in sorted(provider_by_capability.items())
        },
        "median_actionable_evidence_age_at_close_seconds": (
            round(statistics.median(ages), 1) if ages else None
        ),
        "trade_card_completeness": _ratio(
            cards["outcome_counts"].get("complete_trade_card", 0),
            cards["qualifying_option_results"],
        ),
        "trade_card_defects": sum(
            cards["outcome_counts"].get(key, 0)
            for key in ("incomplete_presentation", "path_defect")
        ),
        "stock_proposal_defects": capture["stocks"]["defect_count"],
    }


def _summary(values: list[float]) -> JsonObject:
    if not values:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def validate_targets(inputs: JsonObject, repository_root: Path) -> list[JsonObject]:
    """Unmet targets are permanent: a closure report that records a downgrade
    must be matched by an unmet target, and an unmet target must say so."""
    unmet: list[JsonObject] = []
    for sprint in inputs["sprints"]:
        report = sprint.get("closure_report")
        if report is not None and not (repository_root / report).is_file():
            raise ValueError(f"{sprint['sprint']}: closure report not found: {report}")
        records_downgrade = (
            report is not None
            and "downgrade" in (repository_root / report).read_text(encoding="utf-8").lower()
        )
        sprint_unmet = [item for item in sprint["targets"] if not item["met"]]
        for item in sprint_unmet:
            if item.get("disposition") != "downgraded":
                raise ValueError(f"{sprint['sprint']}: unmet target lacks a downgrade disposition")
        if records_downgrade and not sprint_unmet:
            raise ValueError(
                f"{sprint['sprint']}: closure report records a downgrade but no unmet target "
                "is carried; a downgrade can never be relabelled as success"
            )
        if sprint_unmet and sprint["state"] != "closed_with_downgrade":
            raise ValueError(f"{sprint['sprint']}: unmet target requires closed_with_downgrade")
        unmet.extend({"sprint": sprint["sprint"], **item} for item in sprint_unmet)
    return unmet


def evaluate_gates(
    sessions: list[Session],
    metrics: list[JsonObject],
    data_value: JsonObject,
    inputs: JsonObject,
    minimum_eligible_sessions: int,
) -> list[JsonObject]:
    prior = [item for item in inputs["sprints"] if item["sprint"] != _THIS_SPRINT]
    open_prior = [item["sprint"] for item in prior if item["state"] not in _CLOSED_STATES]
    latest_ledger = sessions[-1].capture["outcomes"] if sessions else None
    ledgers = {
        "user_tracked": latest_ledger or {},
        "system_actionable": sessions[-1].capture.get("system_outcomes", {}) if sessions else {},
    }
    observed_by_source = {
        source: sum(
            horizon["status"] == "observed"
            for candidate in ledger.get("candidates", [])
            for horizon in candidate["horizons"]
        )
        for source, ledger in ledgers.items()
    }
    observed = sum(observed_by_source.values())
    drops = sum(item["unexplained_drop_count"] for item in metrics)
    defects = sum(item["trade_card_defects"] + item["stock_proposal_defects"] for item in metrics)

    def gate(gate_id: str, state: str, detail: str) -> JsonObject:
        return {"gate": gate_id, "state": state, "detail": detail}

    ledger_status = latest_ledger["ledger_status"] if latest_ledger else "no_captures"
    return [
        gate(
            "prior_sprints_closed",
            PASS if not open_prior else PENDING,
            "all closed" if not open_prior else f"open: {', '.join(open_prior)}",
        ),
        gate(
            "forward_ledger_deployed",
            PASS if ledger_status == LEDGER_AVAILABLE else PENDING,
            f"latest eligible capture ledger_status={ledger_status}",
        ),
        gate(
            "forward_outcome_observed",
            PASS if observed else PENDING,
            "observed horizons in the latest readable ledgers, by source (never pooled): "
            + ", ".join(f"{key}={value}" for key, value in observed_by_source.items()),
        ),
        gate(
            "aoy_measured",
            PASS if len(sessions) >= minimum_eligible_sessions else PENDING,
            f"{len(sessions)} eligible session(s), required {minimum_eligible_sessions}",
        ),
        gate(
            "zero_unexplained_drops",
            FAIL if drops else PASS if sessions else PENDING,
            f"{drops} unexplained drop(s) across eligible sessions",
        ),
        gate(
            "presentation_defect_free",
            FAIL if defects else PASS if sessions else PENDING,
            f"{defects} trade-card/stock-proposal defect(s) across eligible sessions",
        ),
        gate(
            "oi07_data_value_complete",
            PASS if data_value["verdict"] == "complete" else PENDING,
            f"OI-07 verdict={data_value['verdict']}",
        ),
        gate(
            "no_open_corrections",
            FAIL if inputs["open_corrections"] else PASS,
            f"{len(inputs['open_corrections'])} open correction(s)",
        ),
    ]


def build_closure(
    captures: list[JsonObject],
    data_value: JsonObject,
    inputs: JsonObject,
    *,
    repository_root: Path,
    minimum_eligible_sessions: int = DEFAULT_MINIMUM_ELIGIBLE_SESSIONS,
) -> JsonObject:
    unmet = validate_targets(inputs, repository_root)
    sessions = [item for item in select_sessions(captures) if item.eligible]
    metrics = [session_metrics(item) for item in sessions]
    gates = evaluate_gates(sessions, metrics, data_value, inputs, minimum_eligible_sessions)
    states = {item["state"] for item in gates}
    if FAIL in states:
        verdict = "reopen_required"
    elif PENDING in states:
        verdict = "observation_pending"
    else:
        verdict = "closure_ready_with_downgrades" if unmet else "closure_ready"
    body: JsonObject = {
        "report_kind": "program_closure",
        "report_version": REPORT_VERSION,
        "program": inputs["program"],
        "verdict": verdict,
        "gates": gates,
        "unmet_targets": unmet,
        "sprints": [
            {key: item[key] for key in ("sprint", "state", "closure_report")}
            for item in inputs["sprints"]
        ],
        "aoy": {
            "total": _summary([float(item["aoy"]) for item in metrics]),
            "option": _summary([float(item["aoy_option"]) for item in metrics]),
            "stock": _summary([float(item["aoy_stock"]) for item in metrics]),
        },
        "per_session": metrics,
        "forward_outcomes": data_value["forward_outcomes"],
        "system_forward_outcomes": data_value.get(
            "system_forward_outcomes", {"ledger_status": "not_captured", "by_strategy": {}}
        ),
        "data_value_verdict": data_value["verdict"],
        "data_value_checksum": data_value["report_checksum"],
        "paid_capability_gaps": [
            {
                "required_capability": row["required_capability"],
                "observed_rows_resolvable": row["observed_rows_resolvable"],
                "observed_rows_partially_resolvable": row["observed_rows_partially_resolvable"],
                "blocked_decisions": row["blocked_decisions"],
            }
            for row in data_value["paid_capability_gaps"]
        ],
        "next_product_decisions": inputs["next_product_decisions"],
    }
    body["report_checksum"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def _mean_of(metrics: list[JsonObject], key: str) -> str:
    values = [item[key] for item in metrics if item[key] is not None]
    return str(round(statistics.fmean(values), 4)) if values else "not measured"


def render_markdown(report: JsonObject) -> str:
    metrics = report["per_session"]
    lines = [
        f"# {report['program']} — Program Closure Report",
        "",
        f"- **Verdict:** `{report['verdict']}`",
        f"- **Report checksum:** `{report['report_checksum']}`",
        f"- **OI-07 data-value verdict:** `{report['data_value_verdict']}` "
        f"(`{report['data_value_checksum'][:12]}`)",
        "",
        "## Evidence gates",
        "",
        "| Gate | State | Detail |",
        "|---|---|---|",
    ]
    lines += [f"| {g['gate']} | **{g['state']}** | {g['detail']} |" for g in report["gates"]]
    lines += ["", "## Unmet / downgraded targets", ""]
    lines += [
        f"- **UNMET (downgraded)**: {item['sprint']}: {item['target']}. Achieved: "
        f"{item['achieved']}. This is not a success."
        for item in report["unmet_targets"]
    ] or ["- none"]
    lines += ["", "## Sprints", "", "| Sprint | State | Closure report |", "|---|---|---|"]
    lines += [
        f"| {item['sprint']} | {item['state']} | {item['closure_report'] or '—'} |"
        for item in report["sprints"]
    ]
    aoy = report["aoy"]
    lines += [
        "",
        "## AOY and coverage",
        "",
        "AOY is the count of complete, currently actionable proposals per eligible session, "
        "measured without lowering any gate.",
        "",
        f"- AOY total: {json.dumps(aoy['total'])}",
        f"- AOY options: {json.dumps(aoy['option'])}",
        f"- AOY stocks: {json.dumps(aoy['stock'])}",
        f"- Evaluation coverage (mean): {_mean_of(metrics, 'evaluation_coverage')}",
        f"- Strategy evaluation completion rate (mean): "
        f"{_mean_of(metrics, 'strategy_evaluation_completion_rate')}",
        f"- Constructible rate after qualifying signals (mean): "
        f"{_mean_of(metrics, 'constructible_rate_after_qualifying')}",
        f"- Trade-card completeness (mean): {_mean_of(metrics, 'trade_card_completeness')}",
        f"- Median actionable evidence age at session close, seconds (mean of sessions): "
        f"{_mean_of(metrics, 'median_actionable_evidence_age_at_close_seconds')}",
        f"- Unexplained drops (total): {sum(item['unexplained_drop_count'] for item in metrics)}",
        "",
        "| Session | SHA | AOY | Options | Stocks | Coverage | Completion | Constructible "
        "| Provider-limited |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in metrics:
        lines.append(
            f"| {item['session_date']} | `{item['production_sha'][:7]}` | {item['aoy']} | "
            f"{item['aoy_option']} | {item['aoy_stock']} | {item['evaluation_coverage']} | "
            f"{item['strategy_evaluation_completion_rate']} | "
            f"{item['constructible_rate_after_qualifying']} | "
            f"{json.dumps(item['provider_limited_rate_by_capability'])} |"
        )
    if not metrics:
        lines.append("| — | — | no eligible sessions captured | | | | | | |")
    lines += ["", "## Forward-outcome corpus", ""]
    for label, outcomes in (
        ("System-actionable (ND-01)", report["system_forward_outcomes"]),
        ("User-tracked", report["forward_outcomes"]),
    ):
        lines.append(f"- **{label}**, ledger `{outcomes['ledger_status']}`")
        for name, item in outcomes.get("by_strategy", {}).items():
            lines.append(
                f"  - {name}: {item['tracked']} subject(s); horizons "
                f"{json.dumps(item['status_counts'])}; "
                f"n={item['observed_with_modeled_pnl']} with modeled P&L"
            )
    lines += ["", "## Remaining quantified data/provider blockers", ""]
    for row in report["paid_capability_gaps"]:
        lines.append(
            f"- {row['required_capability']}: resolvable rows "
            f"{json.dumps(row['observed_rows_resolvable'])}; partially "
            f"{json.dumps(row['observed_rows_partially_resolvable'])}; blocks "
            f"{', '.join(row['blocked_decisions']) or 'none'}"
        )
    lines += ["", "## Genuine next product decisions", ""]
    lines += [
        f"- **{item['id']}** ({item['owner']}): {item['decision']}. {item['why']}"
        for item in report["next_product_decisions"]
    ]
    return "\n".join(lines).rstrip() + "\n"


def _load(path: Path) -> JsonObject:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--data-value", type=Path, required=True)
    parser.add_argument(
        "--inputs",
        type=Path,
        default=Path("project/research/OUTCOME-INTELLIGENCE-001/program-closure-inputs-v1.json"),
    )
    parser.add_argument(
        "--minimum-eligible-sessions", type=int, default=DEFAULT_MINIMUM_ELIGIBLE_SESSIONS
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    report = build_closure(
        [_load(path) for path in sorted(args.captures.glob("*.json"))],
        _load(args.data_value),
        _load(args.inputs),
        repository_root=Path.cwd(),
        minimum_eligible_sessions=args.minimum_eligible_sessions,
    )
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output_markdown.write_text(render_markdown(report))
    return 0 if report["verdict"].startswith("closure_ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
