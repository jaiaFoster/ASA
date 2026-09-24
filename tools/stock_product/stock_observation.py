"""Capture a sanitized stock/ETF proposal observation (SP-06).

For every strategy whose declared structure is ``none``, pages its active
results and fetches each one's stock proposal through the same read-only
surfaces the Intelligence Console renders. It checks each proposal for
complete presentation or typed unknowns. It never refreshes, acquires,
tracks, or mutates anything.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from tools.options_product.founder_utility import Fetch, JsonObject, http_fetcher

_STATUSES = frozenset({"actionable", "no_action", "unknown"})


def proposal_gaps(proposal: JsonObject) -> list[str]:
    """Every missing element of the program's stock "done" contract."""
    gaps = [
        f"missing:{field}"
        for field in (
            "instrument",
            "strategy_id",
            "strategy_version",
            "evidence_observed_at",
            "freshness",
            "evaluation_state",
        )
        if not proposal.get(field)
    ]
    gaps.extend(
        f"empty:{field}" for field in ("rationale", "invalidation_notes") if not proposal.get(field)
    )
    if proposal.get("status") not in _STATUSES:
        gaps.append("invalid:status")
    for value, reason in (("action", "action_reason"), ("allocation", "allocation_reason")):
        if (proposal.get(value) is None) == (proposal.get(reason) is None):
            gaps.append(f"untyped:{value}")
    if proposal.get("status") == "actionable" and proposal.get("action") is None:
        gaps.append("invalid:actionable_without_action")
    if proposal.get("status") == "unknown" and not proposal.get("unknown_reasons"):
        gaps.append("untyped:unknown")
    return gaps


def capture_stock_observation(
    fetch: Fetch, *, production_sha: str, captured_at: datetime
) -> JsonObject:
    status, version = fetch("/api/v1/version")
    deployed = str(version.get("release_sha") or "") if status == 200 else ""
    if deployed != production_sha:
        raise RuntimeError(
            f"deployed SHA mismatch: expected {production_sha}, observed {deployed or 'unset'}"
        )
    status, capabilities = fetch("/api/v1/capabilities")
    if status != 200:
        raise RuntimeError(f"capabilities returned HTTP {status}")
    stock_signals = sorted(
        str(item["signal_id"]) for item in capabilities["signals"] if item["structure"] == "none"
    )
    observations: list[JsonObject] = []
    for signal in stock_signals:
        status, page = fetch(
            "/api/v1/screening?"
            + urlencode({"signal": signal, "active_only": "true", "limit": 500, "offset": 0})
        )
        if status != 200:
            raise RuntimeError(f"screening page for {signal!r} returned HTTP {status}")
        if int(page["total"]) > len(page["results"]):
            raise RuntimeError(f"stock signal {signal!r} exceeds one bounded page")
        for row in sorted(page["results"], key=lambda item: str(item["symbol"])):
            symbol = str(row["symbol"])
            status, proposal = fetch(
                f"/api/v1/screening/{quote(signal, safe='')}/{quote(symbol, safe='')}"
                "/stock-proposal"
            )
            gaps = proposal_gaps(proposal) if status == 200 else [f"stock_proposal_http_{status}"]
            observations.append(
                {
                    "signal_id": signal,
                    "symbol": symbol,
                    "observation_id": row.get("observation_id"),
                    "status": proposal.get("status") if status == 200 else None,
                    "action": proposal.get("action") if status == 200 else None,
                    "action_reason": proposal.get("action_reason") if status == 200 else None,
                    "unknown_reasons": proposal.get("unknown_reasons") if status == 200 else None,
                    "freshness": proposal.get("freshness") if status == 200 else None,
                    "evidence_age_seconds": (
                        proposal.get("evidence_age_seconds") if status == 200 else None
                    ),
                    "gaps": gaps,
                }
            )
    counts: dict[str, int] = {}
    for item in observations:
        key = str(item["status"])
        counts[key] = counts.get(key, 0) + 1
    defects = sum(bool(item["gaps"]) for item in observations)
    verdict = (
        "defect_reopen_correction"
        if defects
        else "actionable_stock_path_observed"
        if counts.get("actionable")
        else "typed_path_only_awaiting_actionable"
        if observations
        else "no_stock_results"
    )
    return {
        "artifact_version": "1.0.0",
        "sprint": "STOCK-PRODUCT-001",
        "ticket": "SP-06",
        "production_sha": production_sha,
        "captured_at": captured_at.astimezone(UTC).isoformat(),
        "stock_signals": stock_signals,
        "status_counts": dict(sorted(counts.items())),
        "defect_count": defects,
        "verdict": verdict,
        "observations": observations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-env", default="ASA_AGENT_API_TOKEN")
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"required token environment variable {args.token_env!r} is unset")
    artifact = capture_stock_observation(
        http_fetcher(args.base_url, token),
        production_sha=args.production_sha,
        captured_at=datetime.now(UTC),
    )
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0 if artifact["verdict"] != "defect_reopen_correction" else 1


if __name__ == "__main__":
    raise SystemExit(main())
