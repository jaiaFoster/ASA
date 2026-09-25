"""Capture one market session's program evidence (OI-07 / program closure input).

One read-only capture per eligible session composes the existing collectors:

- the OT-06 funnel census, for every active option row;
- the OP-07 trade-card traversal, for qualifying option rows;
- the SP-06 stock-proposal observation;
- the forward-outcome ledger (tracked candidates and their recorded horizons).

It never refreshes, tracks, acquires, or mutates anything. The ledger is read
through ``/api/v1/portfolio/tracked-candidates/{id}/outcomes``. If that route
is not deployed, the capture records ``ledger_status`` as unavailable and
never records zero outcomes.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import quote

from tools.options_product.founder_utility import (
    Fetch,
    JsonObject,
    capture_founder_utility,
    http_fetcher,
)
from tools.options_truth.funnel_census import capture_census
from tools.stock_product.stock_observation import capture_stock_observation

ARTIFACT_KIND = "program_session_capture"
ARTIFACT_VERSION = "1.0.0"
LEDGER_AVAILABLE = "available"
LEDGER_NOT_DEPLOYED = "outcome_route_not_deployed"


def _outcome_ledger(fetch: Fetch) -> JsonObject:
    status, body = fetch("/api/v1/portfolio/tracked-candidates")
    # This endpoint returns a JSON array, not an object.
    candidates = cast(list[JsonObject], body)
    if status != 200:
        return {"ledger_status": f"tracked_candidates_http_{status}", "candidates": []}
    rows: list[JsonObject] = []
    for candidate in sorted(candidates, key=lambda item: str(item["id"])):
        status, body = fetch(
            f"/api/v1/portfolio/tracked-candidates/{quote(str(candidate['id']), safe='')}/outcomes"
        )
        if status == 404 and body.get("detail") == "Not Found":
            # FastAPI's route-level 404 (no structured error): the endpoint is
            # not deployed. An unknown candidate returns a typed error instead.
            return {"ledger_status": LEDGER_NOT_DEPLOYED, "candidates": []}
        if status != 200:
            return {"ledger_status": f"outcomes_http_{status}", "candidates": []}
        rows.append(
            {
                "candidate_id": str(candidate["id"]),
                "strategy_id": candidate["strategy_id"],
                "symbol": candidate["symbol"],
                "tracked_at": candidate["tracked_at"],
                "has_frozen_proposal": candidate.get("resolved_proposal_identity") is not None,
                "horizons": [
                    {
                        "horizon_id": item["horizon_id"],
                        "status": item["status"],
                        "due_at": item.get("due_at"),
                        "has_modeled_pnl": item.get("modeled_pnl") is not None,
                    }
                    for item in body.get("outcomes", [])
                ],
            }
        )
    return {"ledger_status": LEDGER_AVAILABLE, "candidates": rows}


def _session_date(fetch: Fetch) -> str | None:
    """The newest economic session date among active rows (first page suffices)."""
    status, page = fetch("/api/v1/screening?active_only=true&limit=500&offset=0")
    if status != 200:
        raise RuntimeError(f"screening page returned HTTP {status}")
    dates = Counter(
        str(row["market_session_date"]) for row in page["results"] if row.get("market_session_date")
    )
    return max(dates) if dates else None


def capture_program_session(
    fetch: Fetch, *, production_sha: str, captured_at: datetime
) -> JsonObject:
    census = capture_census(fetch, production_sha=production_sha, captured_at=captured_at)
    trade_cards = capture_founder_utility(
        fetch, production_sha=production_sha, captured_at=captured_at
    )
    stocks = capture_stock_observation(
        fetch, production_sha=production_sha, captured_at=captured_at
    )
    return {
        "artifact_kind": ARTIFACT_KIND,
        "artifact_version": ARTIFACT_VERSION,
        "production_sha": production_sha,
        "captured_at": captured_at.astimezone(UTC).isoformat(),
        "session_date": _session_date(fetch),
        "census": census,
        "trade_cards": {key: value for key, value in trade_cards.items() if key != "observations"}
        | {
            "observations": [
                {
                    key: item.get(key)
                    for key in ("signal_id", "symbol", "outcome", "terminal_state", "gaps")
                }
                for item in trade_cards["observations"]
            ]
        },
        "stocks": stocks,
        "outcomes": _outcome_ledger(fetch),
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
    artifact = capture_program_session(
        http_fetcher(args.base_url, token),
        production_sha=args.production_sha,
        captured_at=datetime.now(UTC),
    )
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
