"""SP-08A real-session classification of the seven selected strategies.

Read-only. After the Founder deploys the exact-main release, this reads the
production latest-state rows for each selected strategy and classifies the
strategy for one observed session window:

- ``LIVE_EVALUABLE``: at least one row in the window is a completed
  evaluation (PASS, or a due evaluation that resolved to a non-pass verdict).
- ``LIVE_TYPED_DATA_BLOCKER``: the graph executed but every evaluated row
  carries a typed evidence blocker (MISSING_DATA with a named reason).
- ``NOT_DUE``: every row in the window is an explicit not-due decision
  (``decision.state == NO_ACTION`` or verdict ``NO_ACTION``).
  A complete cross-subject family whose registered due callback is false
  at every 10-minute instant of the window is also ``NOT_DUE`` without rows:
  its scheduler writes nothing on non-formation days.
- ``UNOBSERVED``: no row was written in the window. This is never a closure
  class; it means the strategy was not observed and the proof fails.

A row whose typed reason is the generic subject-preparation failure is an
unexplained exception, never a data blocker. The proof passes only when the
deployed SHA equals the expected release, every strategy is classified into
one of the three closure classes, and there are zero exceptions. It never
refreshes, tracks, acquires or mutates anything.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from tools.options_product.founder_utility import Fetch, JsonObject, http_fetcher

ARTIFACT_KIND = "strategy_production_release_classification"
ARTIFACT_VERSION = "1.0.0"

SELECTED_STRATEGIES: tuple[str, ...] = (
    "event_vol_gxz_preea_straddle_to_expiry",
    "index_buywrite_cboe_bxm",
    "index_putwrite_cboe_put",
    "index_putwrite_cboe_puty",
    "index_short_vol_scs_near_atm_straddle",
    "xs_option_heston_straddle_momentum_lowcost",
    "xs_option_zhan_neg_lnprice_dn_call",
)

LIVE_EVALUABLE = "LIVE_EVALUABLE"
LIVE_TYPED_DATA_BLOCKER = "LIVE_TYPED_DATA_BLOCKER"
NOT_DUE = "NOT_DUE"
UNOBSERVED = "UNOBSERVED"
CLOSURE_CLASSES = frozenset({LIVE_EVALUABLE, LIVE_TYPED_DATA_BLOCKER, NOT_DUE})

_EXCEPTION_REASONS = frozenset({"subject_preparation_failed"})
_TYPED_GAP_PREFIX = "typed unknown evidence gap: "
_PAGE_LIMIT = 500


def blocker_code(blocker: str) -> str:
    """The typed reason code inside a persisted blocker string."""
    code = blocker.removeprefix(_TYPED_GAP_PREFIX)
    return code.split(" (", 1)[0].strip()


def classify_row(row: JsonObject) -> str:
    """Classify one latest-state row: a closure class or ``EXCEPTION``."""
    metrics = row.get("metrics") or {}
    codes = [blocker_code(str(item)) for item in row.get("blockers") or ()]
    if any(code in _EXCEPTION_REASONS for code in codes):
        return "EXCEPTION"
    if row.get("verdict") == "NO_ACTION" or metrics.get("decision.state") == "NO_ACTION":
        return NOT_DUE
    if row.get("evaluation_state") == "missing_data":
        # MISSING_DATA without a named reason is not a typed blocker.
        return LIVE_TYPED_DATA_BLOCKER if codes else "EXCEPTION"
    if row.get("evaluation_state") in {"pass", "no_signal"}:
        return LIVE_EVALUABLE
    return "EXCEPTION"


def classify_strategy(rows: list[JsonObject]) -> str:
    classes = {classify_row(row) for row in rows} - {"EXCEPTION"}
    if not rows or not classes:
        return UNOBSERVED
    for name in (LIVE_EVALUABLE, LIVE_TYPED_DATA_BLOCKER, NOT_DUE):
        if name in classes:
            return name
    return UNOBSERVED


def family_due_in_window(strategy_id: str, window_start: datetime, window_end: datetime) -> bool:
    """Whether a registered complete-family due callback fires inside the window.

    Strategies without a family-due callback are always considered due here
    (their absence of rows is then UNOBSERVED, never NOT_DUE).
    """
    from strategy_runtime.adapters import build_migrated_shadow_registry

    instant = window_start
    while instant <= window_end:
        registry = build_migrated_shadow_registry(instant)
        if not registry.is_registered(strategy_id):
            return True
        due = getattr(registry.binding_for(strategy_id), "cross_subject_family_due", None)
        if due is None or due(instant):
            return True
        instant += timedelta(minutes=10)
    return False


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _rows(fetch: Fetch, strategy_id: str) -> list[JsonObject]:
    rows: list[JsonObject] = []
    total: int | None = None
    while total is None or len(rows) < total:
        status, page = fetch(
            "/api/v1/screening?"
            + urlencode(
                {
                    "signal": strategy_id,
                    "active_only": "true",
                    "limit": _PAGE_LIMIT,
                    "offset": len(rows),
                }
            )
        )
        if status != 200:
            raise RuntimeError(f"screening page for {strategy_id!r} returned HTTP {status}")
        total = int(page["total"])
        batch = list(page["results"])
        if not batch and len(rows) < total:
            raise RuntimeError("screening pagination ended before authoritative total")
        rows.extend(batch)
    return rows


def classify_release(
    fetch: Fetch,
    *,
    production_sha: str,
    window_start: datetime,
    window_end: datetime,
    captured_at: datetime,
) -> JsonObject:
    if window_start.tzinfo is None or window_end.tzinfo is None:
        raise ValueError("session window bounds must be timezone-aware")
    status, version = fetch("/api/v1/version")
    deployed = str(version.get("release_sha") or "") if status == 200 else ""
    status, capabilities = fetch("/api/v1/capabilities")
    if status != 200:
        raise RuntimeError(f"capabilities returned HTTP {status}")
    registered = {str(item["signal_id"]) for item in capabilities["signals"]}
    strategies: dict[str, JsonObject] = {}
    for strategy_id in SELECTED_STRATEGIES:
        in_window = [
            row
            for row in (_rows(fetch, strategy_id) if strategy_id in registered else [])
            if window_start <= _parse(str(row["updated_at"])) <= window_end
        ]
        row_classes = Counter(classify_row(row) for row in in_window)
        blocker_codes = Counter(
            blocker_code(str(item)) for row in in_window for item in row.get("blockers") or ()
        )
        classification = classify_strategy(in_window)
        family_not_due = not in_window and not family_due_in_window(
            strategy_id, window_start, window_end
        )
        if family_not_due:
            classification = NOT_DUE
        strategies[strategy_id] = {
            "registered": strategy_id in registered,
            "rows_in_window": len(in_window),
            "classification": classification,
            "family_not_due_in_window": family_not_due,
            "row_classes": dict(sorted(row_classes.items())),
            "exception_rows": sorted(
                str(row["symbol"]) for row in in_window if classify_row(row) == "EXCEPTION"
            ),
            "blocker_codes": dict(sorted(blocker_codes.items())),
        }
    failures: list[str] = []
    if deployed != production_sha:
        failures.append(f"deployed_sha_mismatch:{deployed or 'unset'}")
    for strategy_id, item in strategies.items():
        if not item["registered"]:
            failures.append(f"not_registered:{strategy_id}")
        if item["classification"] not in CLOSURE_CLASSES:
            failures.append(f"unobserved:{strategy_id}")
        if item["exception_rows"]:
            failures.append(f"exceptions:{strategy_id}:{len(item['exception_rows'])}")
    return {
        "artifact_kind": ARTIFACT_KIND,
        "artifact_version": ARTIFACT_VERSION,
        "sprint": "STRATEGY-PRODUCTION-001",
        "ticket": "SP-08A",
        "production_sha": production_sha,
        "deployed_sha": deployed,
        "window_start": window_start.astimezone(UTC).isoformat(),
        "window_end": window_end.astimezone(UTC).isoformat(),
        "captured_at": captured_at.astimezone(UTC).isoformat(),
        "strategies": strategies,
        "failures": failures,
        "verdict": "pass" if not failures else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--window-start", required=True, help="ISO-8601 with offset")
    parser.add_argument("--window-end", required=True, help="ISO-8601 with offset")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--token-env", default="ASA_AGENT_API_TOKEN")
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"required token environment variable {args.token_env!r} is unset")
    artifact = classify_release(
        http_fetcher(args.base_url, token),
        production_sha=args.production_sha,
        window_start=_parse(args.window_start),
        window_end=_parse(args.window_end),
        captured_at=datetime.now(UTC),
    )
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0 if artifact["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
