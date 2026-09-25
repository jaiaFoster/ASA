"""Deterministic OI-07 data-value report over accumulated session captures.

Inputs, all files, all replayable:

- program session captures (``session_capture.py``), one or more per session;
- the data-adequacy decision artifact (its ``capability_gap_matrix``);
- the declared blocked-decision registry.

Output: a JSON report and its Markdown rendering. Identical inputs give
byte-identical outputs. The report measures what the corpus shows, and it
refuses the ``complete`` verdict until the corpus is sufficient. It informs a
later Founder procurement decision and never purchases or integrates data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_data.session_calendar import UsEquitySessionCalendar
from tools.outcome_intelligence.reason_taxonomy import (
    INTERNAL,
    PROVIDER,
    UNCLASSIFIED,
    classify,
    known_gaps,
    reason_code,
)
from tools.outcome_intelligence.session_capture import ARTIFACT_KIND, LEDGER_AVAILABLE

JsonObject = dict[str, Any]

REPORT_VERSION = "1.0.0"
DEFAULT_MINIMUM_ELIGIBLE_SESSIONS = 5
ACTIONABLE_TERMINAL = "actionable_opportunity"
FORWARD_SAMPLE_GUARD = 30  # Mirrors the OI-06 ordering guard.


@dataclass(frozen=True, slots=True)
class Session:
    session_date: str
    capture: JsonObject
    eligible: bool
    ineligible_reason: str | None


def _load(path: Path) -> JsonObject:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def select_sessions(
    captures: list[JsonObject], calendar: UsEquitySessionCalendar | None = None
) -> list[Session]:
    """Keep the latest capture per session date and judge its eligibility.

    A capture is eligible only if its date is a US equity session and it was
    taken after that session's close, so it reflects a complete cycle.
    """
    resolved = calendar or UsEquitySessionCalendar()
    latest: dict[str, JsonObject] = {}
    for capture in captures:
        if capture.get("artifact_kind") != ARTIFACT_KIND:
            raise ValueError("not a program session capture")
        key = str(capture.get("session_date"))
        if key not in latest or capture["captured_at"] > latest[key]["captured_at"]:
            latest[key] = capture
    sessions: list[Session] = []
    for key in sorted(latest):
        capture = latest[key]
        reason: str | None = None
        try:
            market = resolved.session(date.fromisoformat(key))
        except ValueError:
            market = None
        if market is None:
            reason = "not_a_market_session"
        elif datetime.fromisoformat(capture["captured_at"]) < market.closes_at:
            reason = "captured_before_session_close"
        sessions.append(Session(key, capture, reason is None, reason))
    return sessions


def _option_signals(capture: JsonObject) -> dict[str, JsonObject]:
    return dict(capture["census"]["strategies"])


def session_opportunities(capture: JsonObject) -> dict[str, JsonObject]:
    """Per-strategy active, qualifying, and actionable counts for one capture."""
    counts: dict[str, JsonObject] = {}
    for signal, census in _option_signals(capture).items():
        qualifying = capture["trade_cards"]["signals"].get(signal, {})
        counts[signal] = {
            "asset_class": "option",
            "active": census["active_total"],
            "qualifying": qualifying.get("qualifying_verdict_count", 0),
            "actionable": census["terminal_counts"].get(ACTIONABLE_TERMINAL, 0),
        }
    for signal in capture["stocks"]["stock_signals"]:
        rows = [item for item in capture["stocks"]["observations"] if item["signal_id"] == signal]
        actionable = sum(item["status"] == "actionable" for item in rows)
        counts[signal] = {
            "asset_class": "stock",
            "active": len(rows),
            "qualifying": actionable,
            "actionable": actionable,
        }
    return dict(sorted(counts.items()))


def session_losses(capture: JsonObject) -> list[JsonObject]:
    """Every non-actionable outcome as (strategy, code, count, classification)."""
    losses: dict[tuple[str, str], int] = defaultdict(int)
    for signal, census in _option_signals(capture).items():
        for key, count in census["terminal_reason_counts"].items():
            terminal, _, reason = key.partition(":")
            if terminal == ACTIONABLE_TERMINAL:
                continue
            losses[(signal, reason_code(reason))] += count
    for item in capture["stocks"]["observations"]:
        if item["status"] == "no_action":
            losses[(item["signal_id"], "no_action")] += 1
        elif item["status"] == "unknown":
            for code in item.get("unknown_reasons") or ["untyped_unknown"]:
                losses[(item["signal_id"], reason_code(str(code)))] += 1
    rows: list[JsonObject] = []
    for (signal, code), count in sorted(losses.items()):
        kind = classify(code)
        rows.append(
            {
                "strategy": signal,
                "reason": code,
                "count": count,
                "category": kind.category,
                "capability": kind.capability,
                "gap": kind.gap,
                "paid_data_could_resolve": kind.paid_data_could_resolve,
            }
        )
    return rows


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def opportunity_counts(sessions: list[Session]) -> JsonObject:
    per_session = {item.session_date: session_opportunities(item.capture) for item in sessions}
    strategies = sorted({name for counts in per_session.values() for name in counts})
    summary: JsonObject = {}
    for name in strategies:
        present = [counts[name] for counts in per_session.values() if name in counts]
        summary[name] = {
            "asset_class": present[-1]["asset_class"],
            "sessions_observed": len(present),
            "actionable_total": sum(item["actionable"] for item in present),
            "qualifying_total": sum(item["qualifying"] for item in present),
            "actionable_mean_per_session": _mean([float(item["actionable"]) for item in present]),
        }
    return {"per_session": per_session, "by_strategy": summary}


def capability_attribution(sessions: list[Session]) -> JsonObject:
    by_session = {item.session_date: session_losses(item.capture) for item in sessions}
    category_totals: dict[str, int] = defaultdict(int)
    capability_totals: dict[str, int] = defaultdict(int)
    reason_totals: dict[tuple[str, str], JsonObject] = {}
    for rows in by_session.values():
        for row in rows:
            category_totals[row["category"]] += row["count"]
            if row["category"] == PROVIDER:
                capability_totals[row["capability"]] += row["count"]
            key = (row["strategy"], row["reason"])
            entry = reason_totals.setdefault(key, {**row, "count": 0, "sessions": 0})
            entry["count"] += row["count"]
            entry["sessions"] += 1
    rows = [reason_totals[key] for key in sorted(reason_totals)]
    return {
        "category_totals": dict(sorted(category_totals.items())),
        "provider_capability_totals": dict(sorted(capability_totals.items())),
        "reasons": rows,
        "unclassified": [row for row in rows if row["category"] == UNCLASSIFIED],
        "asa_internal": [row for row in rows if row["category"] == INTERNAL],
    }


_NOT_CAPTURED = {"ledger_status": "not_captured", "candidates": []}


def forward_outcome_samples(sessions: list[Session], key: str = "outcomes") -> JsonObject:
    """Sample sizes from the newest capture whose ledger (``key``) was readable.

    ``outcomes`` is the user-tracked corpus and ``system_outcomes`` the ND-01
    system-actionable corpus. The two are always reported separately.
    """
    for item in reversed(sessions):
        ledger = item.capture.get(key, _NOT_CAPTURED)
        if ledger["ledger_status"] != LEDGER_AVAILABLE:
            continue
        by_strategy: dict[str, JsonObject] = {}
        for candidate in ledger["candidates"]:
            entry = by_strategy.setdefault(
                candidate["strategy_id"],
                {
                    "tracked": 0,
                    "with_frozen_proposal": 0,
                    "status_counts": defaultdict(int),
                    "observed_with_modeled_pnl": 0,
                },
            )
            entry["tracked"] += 1
            entry["with_frozen_proposal"] += int(candidate["has_frozen_proposal"])
            entry.setdefault("_opportunities", set()).add(
                candidate.get("opportunity_id") or f"row:{candidate['candidate_id']}"
            )
            entry.setdefault("_leg_sets", set()).add(
                "|".join(candidate.get("exact_leg_set") or [f"row:{candidate['candidate_id']}"])
            )
            for horizon in candidate["horizons"]:
                entry["status_counts"][horizon["status"]] += 1
                entry["observed_with_modeled_pnl"] += int(
                    horizon["status"] == "observed" and horizon["has_modeled_pnl"]
                )
        for entry in by_strategy.values():
            counts = entry["status_counts"]
            due = counts.get("observed", 0) + counts.get("missed", 0)
            entry["status_counts"] = dict(sorted(counts.items()))
            # Row count vs distinct opportunities / exact leg sets: a re-enrolled
            # opportunity inflates rows, never the distinct counts.
            entry["distinct_opportunities"] = len(entry.pop("_opportunities"))
            entry["distinct_exact_leg_sets"] = len(entry.pop("_leg_sets"))
            entry["due_horizon_coverage"] = (
                round(counts.get("observed", 0) / due, 4) if due else None
            )
            entry["meets_sample_guard"] = entry["observed_with_modeled_pnl"] >= FORWARD_SAMPLE_GUARD
        return {
            "ledger_status": LEDGER_AVAILABLE,
            "as_of_session": item.session_date,
            "tracked_total": len(ledger["candidates"]),
            "by_strategy": dict(sorted(by_strategy.items())),
            "sample_guard": FORWARD_SAMPLE_GUARD,
        }
    status = (
        sessions[-1].capture.get(key, _NOT_CAPTURED)["ledger_status"] if sessions else "no_captures"
    )
    return {"ledger_status": status, "by_strategy": {}}


def _latest_counts(sessions: list[Session]) -> dict[str, int]:
    """Latest-session loss counts keyed by reason code."""
    if not sessions:
        return {}
    totals: dict[str, int] = defaultdict(int)
    for row in session_losses(sessions[-1].capture):
        totals[row["reason"]] += row["count"]
    return totals


def blocked_decisions(
    sessions: list[Session], registry: JsonObject, adequacy: JsonObject, repository_root: Path
) -> list[JsonObject]:
    latest = _latest_counts(sessions)
    gaps = {row["required_capability"] for row in adequacy["capability_gap_matrix"]}
    rows: list[JsonObject] = []
    for item in registry["decisions"]:
        missing = [ref for ref in item["evidence_refs"] if not (repository_root / ref).is_file()]
        if missing:
            raise ValueError(f"{item['id']}: evidence reference(s) not found: {missing}")
        unknown_gaps = set(item["unlock_gaps"]) - gaps
        if unknown_gaps:
            raise ValueError(
                f"{item['id']}: gap(s) absent from the adequacy artifact: {unknown_gaps}"
            )
        observed = {code: latest.get(code, 0) for code in item.get("observed_reason_codes", [])}
        rows.append(
            {
                **item,
                "latest_session_observed_counts": observed,
                "latest_session_observed_total": sum(observed.values()),
            }
        )
    return rows


def paid_capability_gaps(
    sessions: list[Session], adequacy: JsonObject, decisions: list[JsonObject]
) -> list[JsonObject]:
    matrix = adequacy["capability_gap_matrix"]
    names = {row["required_capability"] for row in matrix}
    unknown = known_gaps() - names
    if unknown:
        raise ValueError(f"taxonomy names gaps absent from the adequacy artifact: {unknown}")
    per_gap: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for session in sessions:
        seen: dict[tuple[str, str], int] = defaultdict(int)
        for row in session_losses(session.capture):
            if row["gap"] is not None:
                seen[(row["gap"], row["paid_data_could_resolve"])] += row["count"]
        for gap in names:
            for resolvable in ("yes", "partially"):
                per_gap[gap][resolvable].append(seen.get((gap, resolvable), 0))
    rows: list[JsonObject] = []
    for row in matrix:
        gap = row["required_capability"]
        counts = per_gap[gap]
        rows.append(
            {
                **row,
                "observed_rows_resolvable": {
                    "latest_session": counts["yes"][-1] if counts["yes"] else None,
                    "mean_per_session": _mean([float(value) for value in counts["yes"]]),
                },
                "observed_rows_partially_resolvable": {
                    "latest_session": counts["partially"][-1] if counts["partially"] else None,
                    "mean_per_session": _mean([float(value) for value in counts["partially"]]),
                },
                "blocked_decisions": sorted(
                    item["id"] for item in decisions if gap in item.get("unlock_gaps", [])
                ),
            }
        )
    return rows


def build_report(
    captures: list[JsonObject],
    adequacy: JsonObject,
    registry: JsonObject,
    *,
    repository_root: Path,
    minimum_eligible_sessions: int = DEFAULT_MINIMUM_ELIGIBLE_SESSIONS,
    calendar: UsEquitySessionCalendar | None = None,
) -> JsonObject:
    sessions = select_sessions(captures, calendar)
    eligible = [item for item in sessions if item.eligible]
    attribution = capability_attribution(eligible)
    outcomes = forward_outcome_samples(eligible)
    decisions = blocked_decisions(eligible, registry, adequacy, repository_root)
    insufficiency: list[str] = []
    if len(eligible) < minimum_eligible_sessions:
        insufficiency.append(
            f"eligible_sessions {len(eligible)} < required {minimum_eligible_sessions}"
        )
    if outcomes["ledger_status"] != LEDGER_AVAILABLE:
        insufficiency.append(f"forward_outcome_ledger {outcomes['ledger_status']}")
    if attribution["unclassified"]:
        insufficiency.append(
            "unclassified_reasons "
            + ",".join(sorted({row["reason"] for row in attribution["unclassified"]}))
        )
    body: JsonObject = {
        "report_kind": "oi07_data_value_report",
        "report_version": REPORT_VERSION,
        "adequacy_artifact": adequacy["artifact_identity"],
        "registry_version": registry["registry_version"],
        "sessions": [
            {
                "session_date": item.session_date,
                "production_sha": item.capture["production_sha"],
                "captured_at": item.capture["captured_at"],
                "eligible": item.eligible,
                "ineligible_reason": item.ineligible_reason,
            }
            for item in sessions
        ],
        "eligible_session_count": len(eligible),
        "minimum_eligible_sessions": minimum_eligible_sessions,
        "opportunity_counts": opportunity_counts(eligible),
        "capability_attribution": attribution,
        "forward_outcomes": outcomes,
        "system_forward_outcomes": forward_outcome_samples(eligible, "system_outcomes"),
        "blocked_decisions": decisions,
        "paid_capability_gaps": paid_capability_gaps(eligible, adequacy, decisions),
        "verdict": "complete" if not insufficiency else "evidence_insufficient",
        "insufficiency": insufficiency,
        "procurement": "none; this report informs a later Founder decision only",
    }
    body["report_checksum"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def render_markdown(report: JsonObject) -> str:
    lines = [
        "# OUTCOME-INTELLIGENCE-001 — OI-07 Data-Value Report",
        "",
        f"- **Verdict:** `{report['verdict']}`",
    ]
    lines += [f"  - insufficient: {item}" for item in report["insufficiency"]]
    lines += [
        f"- **Eligible sessions:** {report['eligible_session_count']} "
        f"(required {report['minimum_eligible_sessions']})",
        f"- **Data-adequacy artifact:** `{report['adequacy_artifact']}`",
        f"- **Report checksum:** `{report['report_checksum']}`",
        f"- **Procurement:** {report['procurement']}",
        "",
        "## Sessions",
        "",
        "| Session | SHA | Captured | Eligible |",
        "|---|---|---|---|",
    ]
    for item in report["sessions"]:
        eligible = "yes" if item["eligible"] else f"no ({item['ineligible_reason']})"
        lines.append(
            f"| {item['session_date']} | `{item['production_sha'][:7]}` | "
            f"{item['captured_at']} | {eligible} |"
        )
    lines += [
        "",
        "## Opportunity counts by strategy",
        "",
        "| Strategy | Asset | Sessions | Qualifying | Actionable | Actionable / session |",
        "|---|---|---|---|---|---|",
    ]
    for name, item in report["opportunity_counts"]["by_strategy"].items():
        lines.append(
            f"| {name} | {item['asset_class']} | {item['sessions_observed']} | "
            f"{item['qualifying_total']} | {item['actionable_total']} | "
            f"{item['actionable_mean_per_session']} |"
        )
    attribution = report["capability_attribution"]
    lines += ["", "## Lost opportunities by cause", "", "| Category | Rows |", "|---|---|"]
    lines += [f"| {key} | {value} |" for key, value in attribution["category_totals"].items()]
    lines += ["", "Provider-capability losses by capability:", ""]
    lines += [
        f"- `{key}`: {value}" for key, value in attribution["provider_capability_totals"].items()
    ] or ["- none observed"]
    lines += [
        "",
        "| Strategy | Reason | Rows | Sessions | Category | Capability | Paid data could resolve |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in attribution["reasons"]:
        lines.append(
            f"| {row['strategy']} | `{row['reason']}` | {row['count']} | {row['sessions']} | "
            f"{row['category']} | {row['capability'] or '—'} | {row['paid_data_could_resolve']} |"
        )
    for title, outcomes in (
        ("Forward-outcome sample sizes: user-tracked", report["forward_outcomes"]),
        (
            "Forward-outcome sample sizes: system-actionable (ND-01)",
            report.get(
                "system_forward_outcomes", {"ledger_status": "not_captured", "by_strategy": {}}
            ),
        ),
    ):
        lines += ["", f"## {title}", "", f"Ledger: `{outcomes['ledger_status']}`"]
        if outcomes["by_strategy"]:
            lines += [
                "",
                "| Strategy | Subjects | Distinct opportunities | Distinct leg sets | "
                "Horizon statuses | Observed with modeled P&L | Due coverage | Meets guard |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for name, item in outcomes["by_strategy"].items():
                lines.append(
                    f"| {name} | {item['tracked']} | {item['distinct_opportunities']} | "
                    f"{item['distinct_exact_leg_sets']} | {json.dumps(item['status_counts'])} | "
                    f"{item['observed_with_modeled_pnl']} | {item['due_horizon_coverage']} | "
                    f"{'yes' if item['meets_sample_guard'] else 'no'} |"
                )
        else:
            lines += ["", "No readable forward-outcome sample. It is not reported as zero."]
    lines += ["", "## Decisions blocked by missing data", ""]
    for item in report["blocked_decisions"]:
        lines += [
            f"### {item['id']}: {item['decision']}",
            "",
            f"- Blocked by: {item['blocked_by']}",
            f"- Unlock: {item['unlock']}",
            f"- Paid data could resolve: **{item['paid_data_could_resolve']}**",
            f"- Latest-session observed rows: {item['latest_session_observed_total']} "
            f"{json.dumps(item['latest_session_observed_counts'])}",
            f"- Evidence: {', '.join(f'`{ref}`' for ref in item['evidence_refs'])}",
            "",
        ]
    lines += ["## Paid-capability gaps (quantified)", ""]
    for row in report["paid_capability_gaps"]:
        lines += [
            f"### {row['required_capability']}",
            "",
            f"- Strategies affected: {', '.join(row['strategies_affected'])}",
            f"- Would better data solve it: {row['would_better_external_data_solve']}",
            "- Observed rows a source could resolve: "
            f"{json.dumps(row['observed_rows_resolvable'])}",
            f"- Observed rows only partially resolvable: "
            f"{json.dumps(row['observed_rows_partially_resolvable'])}",
            f"- Blocked decisions: {', '.join(row['blocked_decisions']) or 'none'}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=Path, required=True, help="directory of captures")
    parser.add_argument(
        "--adequacy",
        type=Path,
        default=Path("project/research/DATA-RELIABILITY-001/data-adequacy-v1.json"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("project/research/OUTCOME-INTELLIGENCE-001/blocked-decisions-v1.json"),
    )
    parser.add_argument(
        "--minimum-eligible-sessions", type=int, default=DEFAULT_MINIMUM_ELIGIBLE_SESSIONS
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    captures = [_load(path) for path in sorted(args.captures.glob("*.json"))]
    report = build_report(
        captures,
        _load(args.adequacy),
        _load(args.registry),
        repository_root=Path.cwd(),
        minimum_eligible_sessions=args.minimum_eligible_sessions,
    )
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output_markdown.write_text(render_markdown(report))
    return 0 if report["verdict"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
