"""Census every active option-strategy row's funnel terminal (OT-06).

Read-only: pages the active latest-state set per signal and fetches each row's
authoritative OT-02 option funnel. Counts terminal state/reason by strategy and
reports every unexplained drop. It never refreshes, acquires, or mutates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from tools.options_product.founder_utility import Fetch, JsonObject, http_fetcher

_PAGE_LIMIT = 500
# A qualifying signal without a current structure assessment has no typed product
# outcome; OT-02 names it but it is still an unexplained loss for OT-06.
_UNEXPLAINED_TERMINALS = frozenset({"structure_unresolved"})


def _error_code(body: JsonObject) -> str:
    detail = body.get("detail")
    return str(detail.get("error_code")) if isinstance(detail, dict) else "unknown_error"


def _terminal_reason_family(reason: str) -> str:
    """Collapse row-specific detail (dates, values) while keeping the typed code."""
    return reason.partition(" (")[0]


def census_signal(fetch: Fetch, signal: str) -> JsonObject | None:
    rows: list[JsonObject] = []
    total: int | None = None
    while total is None or len(rows) < total:
        status, page = fetch(
            "/api/v1/screening?"
            + urlencode(
                {"signal": signal, "active_only": "true", "limit": _PAGE_LIMIT, "offset": len(rows)}
            )
        )
        if status != 200:
            raise RuntimeError(f"screening page for {signal!r} returned HTTP {status}")
        total = int(page["total"])
        batch = list(page["results"])
        if not batch and len(rows) < total:
            raise RuntimeError("screening pagination ended before authoritative total")
        rows.extend(batch)
    terminals: dict[str, int] = {}
    reasons: dict[str, int] = {}
    unexplained: list[JsonObject] = []
    actionable: list[JsonObject] = []
    for row in sorted(rows, key=lambda item: str(item["symbol"])):
        symbol = str(row["symbol"])
        status, funnel = fetch(
            f"/api/v1/screening/{quote(signal, safe='')}/{quote(symbol, safe='')}/option-funnel"
        )
        if status == 404 and _error_code(funnel) == "NO_OPTION_FUNNEL":
            return None
        if status != 200:
            unexplained.append({"symbol": symbol, "reason": f"http_{status}:{_error_code(funnel)}"})
            continue
        terminal = str(funnel.get("terminal_state") or "")
        reason = str(funnel.get("terminal_reason") or "")
        if not terminal or not reason or terminal in _UNEXPLAINED_TERMINALS:
            unexplained.append({"symbol": symbol, "reason": f"{terminal or 'none'}:{reason}"})
        if terminal == "actionable_opportunity":
            actionable.append({"symbol": symbol, "observed_at": str(row.get("observed_at"))})
        terminals[terminal] = terminals.get(terminal, 0) + 1
        key = f"{terminal}:{_terminal_reason_family(reason)}"
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "active_total": total,
        "traced": sum(terminals.values()),
        "terminal_counts": dict(sorted(terminals.items())),
        "terminal_reason_counts": dict(sorted(reasons.items())),
        "unexplained": unexplained,
        "actionable": actionable,
    }


def capture_census(fetch: Fetch, *, production_sha: str, captured_at: datetime) -> JsonObject:
    status, version = fetch("/api/v1/version")
    deployed = str(version.get("release_sha") or "") if status == 200 else ""
    if deployed != production_sha:
        raise RuntimeError(
            f"deployed SHA mismatch: expected {production_sha}, observed {deployed or 'unset'}"
        )
    status, capabilities = fetch("/api/v1/capabilities")
    if status != 200:
        raise RuntimeError(f"capabilities returned HTTP {status}")
    strategies: dict[str, JsonObject] = {}
    for signal in sorted(str(item["signal_id"]) for item in capabilities["signals"]):
        census = census_signal(fetch, signal)
        if census is not None and census["active_total"]:
            strategies[signal] = census
    unexplained_total = sum(len(item["unexplained"]) for item in strategies.values())
    checksum = hashlib.sha256(
        json.dumps(
            {name: item["terminal_reason_counts"] for name, item in strategies.items()},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "artifact_version": "1.0.0",
        "sprint": "OPTIONS-TRUTH-001",
        "ticket": "OT-06",
        "production_sha": production_sha,
        "captured_at": captured_at.astimezone(UTC).isoformat(),
        "strategies": strategies,
        "unexplained_drop_total": unexplained_total,
        "verdict": "pass" if unexplained_total == 0 else "fail_reopen_correction",
        "census_checksum": checksum,
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
    artifact = capture_census(
        http_fetcher(args.base_url, token),
        production_sha=args.production_sha,
        captured_at=datetime.now(UTC),
    )
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0 if artifact["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
