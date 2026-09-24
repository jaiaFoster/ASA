"""Capture a sanitized, bounded Earnings Calendar funnel cohort (OT-03)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JsonObject = dict[str, Any]
FetchJson = Callable[[str], JsonObject]

_PROVIDER_CODES = frozenset(
    {
        "authentication_failed",
        "authorization_failed",
        "entitlement_missing",
        "provider_unavailable",
        "rate_limited",
        "timeout",
        "transport_error",
        "upstream_rate_limited",
        "entitlement_unavailable",
        "transport_failure",
    }
)
_POLICY_CODES = frozenset(
    {
        "no_valid_expiration_pair",
        "expiration_gap_rejected",
        "no_eligible_expiration_pair",
    }
)
_ASA_DEFECT_CODES = frozenset(
    {
        "subject_preparation_failed",
        "strategy_knowledge_construction_failed",
        "unexpected_runtime_exception",
        "malformed_output",
        "strategy_exception",
    }
)


def classify_terminal(row: JsonObject, funnel: JsonObject) -> str:
    """Map one sanitized trace onto OT-03's closed evidence classes."""
    terminal = str(funnel["terminal_state"])
    reason = str(funnel["terminal_reason"]).lower()
    acquisition = funnel.get("acquisition", [])
    codes = {
        str(item.get("missing_reason", "")).lower()
        for item in acquisition
        if isinstance(item, dict)
    }
    tokens = codes | {reason.partition(" (")[0].removeprefix("typed unknown evidence gap: ")}
    if tokens & _ASA_DEFECT_CODES:
        return "asa_defect"
    if tokens & _PROVIDER_CODES:
        return "provider_entitlement_or_coverage"
    if tokens & _POLICY_CODES:
        return "legitimate_temporal_or_policy_absence"
    if terminal in {"structure_unavailable", "structure_unknown"}:
        return "structure_or_market_unavailability"
    if terminal == "strategy_rejected":
        return "true_strategy_rejection"
    if terminal == "actionable_opportunity":
        return "actionable_opportunity"
    canonical = row.get("canonical_facts", {})
    if terminal == "evidence_unavailable" and not canonical.get("earnings_date"):
        return "genuinely_unknown_or_unannounced_event"
    return "asa_defect" if terminal == "structure_unresolved" else "legitimate_unknown"


def select_cohort(
    rows: list[JsonObject],
    *,
    as_of: date,
    recent_days: int,
    future_days: int,
    limit: int,
) -> list[JsonObject]:
    lower = as_of - timedelta(days=recent_days)
    upper = as_of + timedelta(days=future_days)

    def event_date(row: JsonObject) -> date | None:
        raw = row.get("canonical_facts", {}).get("earnings_date")
        try:
            return None if raw is None else date.fromisoformat(str(raw))
        except ValueError:
            return None

    eligible = [
        row for row in rows if (value := event_date(row)) is not None and lower <= value <= upper
    ]
    eligible.sort(
        key=lambda row: (
            abs((event_date(row) - as_of).days),  # type: ignore[operator]
            str(row["symbol"]),
        )
    )
    selected = eligible[:limit]
    selected_symbols = {str(row["symbol"]) for row in selected}
    missing_event = sorted(
        (
            row
            for row in rows
            if event_date(row) is None and str(row["symbol"]) not in selected_symbols
        ),
        key=lambda row: str(row["symbol"]),
    )
    return selected + missing_event[: max(0, limit - len(selected))]


def capture_cohort(
    fetch: FetchJson,
    *,
    production_sha: str,
    captured_at: datetime,
    limit: int = 30,
    recent_days: int = 7,
    future_days: int = 21,
) -> JsonObject:
    version = fetch("/api/v1/version")
    deployed_sha = str(version.get("release_sha") or "")
    if deployed_sha != production_sha:
        raise RuntimeError(
            f"deployed SHA mismatch: expected {production_sha}, observed {deployed_sha or 'unset'}"
        )
    page = fetch(
        "/api/v1/screening?"
        + urlencode(
            {
                "signal": "earnings_calendar",
                "active_only": "true",
                "limit": 500,
                "offset": 0,
            }
        )
    )
    rows = list(page["results"])
    total = int(page["total"])
    offset = len(rows)
    while offset < total:
        next_page = fetch(
            "/api/v1/screening?"
            + urlencode(
                {
                    "signal": "earnings_calendar",
                    "active_only": "true",
                    "limit": 500,
                    "offset": offset,
                }
            )
        )
        batch = list(next_page["results"])
        if not batch:
            raise RuntimeError("screening pagination ended before authoritative total")
        rows.extend(batch)
        offset += len(batch)
    cohort = select_cohort(
        rows,
        as_of=captured_at.date(),
        recent_days=recent_days,
        future_days=future_days,
        limit=limit,
    )
    observations: list[JsonObject] = []
    for row in cohort:
        symbol = str(row["symbol"])
        funnel = fetch(f"/api/v1/screening/earnings_calendar/{symbol}/option-funnel")
        observations.append(
            {
                "symbol": symbol,
                "observation_id": row.get("observation_id"),
                "earnings_date": row.get("canonical_facts", {}).get("earnings_date"),
                "selected_front_expiration": row.get("canonical_facts", {}).get(
                    "selected_front_expiration"
                ),
                "selected_back_expiration": row.get("canonical_facts", {}).get(
                    "selected_back_expiration"
                ),
                "actual_gap_days": row.get("named_derived_facts", {}).get("actual_gap_days"),
                "gate_outcomes": funnel["gate_outcomes"],
                "evaluation_state": funnel["evaluation_state"],
                "signal_verdict": funnel["signal_verdict"],
                "acquisition": funnel["acquisition"],
                "structure_status": funnel["structure_status"],
                "constructibility_reason": funnel["constructibility_reason"],
                "terminal_state": funnel["terminal_state"],
                "terminal_reason": funnel["terminal_reason"],
                "classification": classify_terminal(row, funnel),
            }
        )
    identity_payload = [
        (item["symbol"], item["observation_id"], item["terminal_state"]) for item in observations
    ]
    checksum = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    counts: dict[str, int] = {}
    for item in observations:
        key = str(item["classification"])
        counts[key] = counts.get(key, 0) + 1
    return {
        "artifact_version": "1.0.0",
        "sprint": "OPTIONS-TRUTH-001",
        "ticket": "OT-03",
        "production_sha": production_sha,
        "captured_at": captured_at.astimezone(UTC).isoformat(),
        "source_active_total": total,
        "cohort_size": len(observations),
        "cohort_checksum": checksum,
        "classification_counts": dict(sorted(counts.items())),
        "observations": observations,
    }


def _http_fetcher(base_url: str, token: str) -> FetchJson:
    normalized = base_url.rstrip("/")

    def fetch(path: str) -> JsonObject:
        request = Request(
            normalized + path,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        with urlopen(request, timeout=30) as response:  # noqa: S310 - explicit operator URL
            return json.loads(response.read())

    return fetch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-env", default="ASA_AGENT_API_TOKEN")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--recent-days", type=int, default=7)
    parser.add_argument("--future-days", type=int, default=21)
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"required token environment variable {args.token_env!r} is unset")
    artifact = capture_cohort(
        _http_fetcher(args.base_url, token),
        production_sha=args.production_sha,
        captured_at=datetime.now(UTC),
        limit=args.limit,
        recent_days=args.recent_days,
        future_days=args.future_days,
    )
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
