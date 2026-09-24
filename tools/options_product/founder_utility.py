"""Capture a sanitized Founder-utility trade-card observation (OP-07).

Traverses every active qualifying option-strategy result on an exact deployed
SHA through the same read-only product surfaces the Intelligence Console uses:
option funnel, canonical trade proposal, and deterministic terminal payoff.
It never refreshes, tracks, acquires, or mutates anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from http.client import HTTPException
from pathlib import Path
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

JsonObject = dict[str, Any]
FetchResponse = tuple[int, JsonObject]
Fetch = Callable[[str], FetchResponse]

_QUALIFYING_VERDICTS = frozenset({"PASS", "WATCH"})
_QUANTITY_FIELDS = ("capital_required", "maximum_loss", "maximum_profit", "breakeven")
_QUANTITY_STATES = frozenset({"supported", "undefined", "unknown"})
_PAGE_LIMIT = 500

# Path outcomes. Only the last two falsify OP-07.
COMPLETE_TRADE_CARD = "complete_trade_card"
TYPED_FAILURE_PRESENTATION = "typed_failure_presentation"
INCOMPLETE_PRESENTATION = "incomplete_presentation"
PATH_DEFECT = "path_defect"
_DEFECT_OUTCOMES = frozenset({INCOMPLETE_PRESENTATION, PATH_DEFECT})


def _error_code(body: JsonObject) -> str:
    detail = body.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("error_code") or "unknown_error")
    return "unknown_error"


def trade_card_gaps(proposal: JsonObject) -> list[str]:
    """Return every missing element of the program's options "done" contract."""
    gaps: list[str] = []
    for field in (
        "proposal_identity",
        "originating_result_identity",
        "underlying",
        "strategy_id",
        "strategy_version",
        "structure",
        "modeled_net_debit_or_credit",
        "entry_model_version",
        "entry_calculated_at",
        "liquidity",
        "evidence_snapshot_identity",
        "constructibility",
    ):
        if not proposal.get(field):
            gaps.append(f"missing:{field}")
    for field in ("assumptions", "rationale", "risk_notes", "invalidation_notes"):
        if not proposal.get(field):
            gaps.append(f"empty:{field}")
    legs = proposal.get("legs") or []
    if not legs:
        gaps.append("empty:legs")
    for index, leg in enumerate(legs):
        for field in (
            "canonical_contract_identity",
            "strike",
            "expiration",
            "quantity",
            "quote_observed_at",
        ):
            if not leg.get(field):
                gaps.append(f"leg[{index}].missing:{field}")
        if leg.get("buy_or_sell") not in {"buy", "sell"}:
            gaps.append(f"leg[{index}].invalid:buy_or_sell")
        if leg.get("call_or_put") not in {"call", "put"}:
            gaps.append(f"leg[{index}].invalid:call_or_put")
        # Quotes may be truthfully absent; a midpoint without both sides is not.
        if leg.get("midpoint") is not None and (leg.get("bid") is None or leg.get("ask") is None):
            gaps.append(f"leg[{index}].invalid:midpoint_without_bid_ask")
    for field in _QUANTITY_FIELDS:
        quantity = proposal.get(field)
        if not isinstance(quantity, dict) or quantity.get("state") not in _QUANTITY_STATES:
            gaps.append(f"invalid:{field}")
        elif quantity["state"] == "supported" and quantity.get("value") is None:
            gaps.append(f"unsupported_value:{field}")
        elif quantity["state"] != "supported" and not quantity.get("reason"):
            gaps.append(f"untyped_absence:{field}")
    return gaps


def failure_presentation_gaps(proposal: JsonObject) -> list[str]:
    """A nonconstructible card must show the exact typed blocker, never a bare PASS."""
    return [
        f"missing:{field}"
        for field in ("reason_code", "blocker_category", "user_message", "constructibility")
        if not proposal.get(field)
    ]


def payoff_gaps(payoff: JsonObject) -> list[str]:
    gaps: list[str] = []
    if not payoff.get("points"):
        gaps.append("empty:payoff.points")
    for field in ("payoff_identity", "model_version", "semantics", "entry_fill_assumption"):
        if not payoff.get(field):
            gaps.append(f"missing:payoff.{field}")
    return gaps


def _observe_row(fetch: Fetch, signal: str, row: JsonObject) -> JsonObject | None:
    symbol = str(row["symbol"])
    base = f"/api/v1/screening/{quote(signal, safe='')}/{quote(symbol, safe='')}"
    status, funnel = fetch(f"{base}/option-funnel")
    if status == 404 and _error_code(funnel) == "NO_OPTION_FUNNEL":
        return None
    record: JsonObject = {
        "signal_id": signal,
        "symbol": symbol,
        "observation_id": row.get("observation_id"),
        "signal_verdict": row.get("verdict"),
        "evaluation_state": row.get("evaluation_state"),
    }
    if status != 200:
        return record | {
            "outcome": PATH_DEFECT,
            "gaps": [f"option_funnel_http_{status}:{_error_code(funnel)}"],
        }
    record |= {
        "terminal_state": funnel["terminal_state"],
        "terminal_reason": funnel["terminal_reason"],
        "structure_status": funnel["structure_status"],
    }
    status, proposal = fetch(f"{base}/trade-proposal")
    if status != 200:
        # A qualifying signal whose card cannot be rendered at all is a product-path
        # defect, whether readiness is absent (404) or behind the result (409).
        return record | {
            "outcome": PATH_DEFECT,
            "gaps": [f"trade_proposal_http_{status}:{_error_code(proposal)}"],
        }
    if proposal.get("status") == "unavailable":
        gaps = failure_presentation_gaps(proposal)
        return record | {
            "outcome": INCOMPLETE_PRESENTATION if gaps else TYPED_FAILURE_PRESENTATION,
            "gaps": gaps,
            "reason_code": proposal.get("reason_code"),
            "blocker_category": proposal.get("blocker_category"),
        }
    gaps = trade_card_gaps(proposal)
    if proposal.get("originating_result_identity") != row.get("observation_id"):
        gaps.append("mismatch:originating_result_identity")
    status, payoff = fetch(f"{base}/execution-readiness/terminal-payoff")
    payoff_state: str
    if status == 200:
        gaps.extend(payoff_gaps(payoff))
        payoff_state = "deterministic_terminal_payoff"
    elif status == 422:
        # Typed refusal (e.g. calendar legs with different expirations) is truthful.
        payoff_state = f"typed_unavailable:{_error_code(payoff)}"
    else:
        gaps.append(f"terminal_payoff_http_{status}:{_error_code(payoff)}")
        payoff_state = "defect"
    return record | {
        "outcome": INCOMPLETE_PRESENTATION if gaps else COMPLETE_TRADE_CARD,
        "gaps": gaps,
        "proposal_identity": proposal.get("proposal_identity"),
        "structure": proposal.get("structure"),
        "leg_count": len(proposal.get("legs") or []),
        "modeled_net_debit_or_credit": proposal.get("modeled_net_debit_or_credit"),
        "payoff_state": payoff_state,
    }


def _active_rows(fetch: Fetch, signal: str) -> tuple[list[JsonObject], int]:
    rows: list[JsonObject] = []
    total = None
    while total is None or len(rows) < total:
        status, page = fetch(
            "/api/v1/screening?"
            + urlencode(
                {
                    "signal": signal,
                    "active_only": "true",
                    "limit": _PAGE_LIMIT,
                    "offset": len(rows),
                }
            )
        )
        if status != 200:
            raise RuntimeError(f"screening page for {signal!r} returned HTTP {status}")
        total = int(page["total"])
        batch = list(page["results"])
        if not batch and len(rows) < total:
            raise RuntimeError("screening pagination ended before authoritative total")
        rows.extend(batch)
    return rows, total


def summarize(observations: list[JsonObject]) -> str:
    """Return the closed OP-07 observation verdict."""
    outcomes = {str(item["outcome"]) for item in observations}
    if outcomes & _DEFECT_OUTCOMES:
        return "defect_reopen_correction"
    if COMPLETE_TRADE_CARD in outcomes:
        return "complete_trade_card_path_observed"
    if TYPED_FAILURE_PRESENTATION in outcomes:
        return "typed_failure_path_only_awaiting_constructible"
    return "bounded_no_signal"


def capture_founder_utility(
    fetch: Fetch,
    *,
    production_sha: str,
    captured_at: datetime,
) -> JsonObject:
    status, version = fetch("/api/v1/version")
    deployed_sha = str(version.get("release_sha") or "") if status == 200 else ""
    if deployed_sha != production_sha:
        raise RuntimeError(
            f"deployed SHA mismatch: expected {production_sha}, observed {deployed_sha or 'unset'}"
        )
    status, capabilities = fetch("/api/v1/capabilities")
    if status != 200:
        raise RuntimeError(f"capabilities returned HTTP {status}")
    signals = sorted(str(item["signal_id"]) for item in capabilities["signals"])
    per_signal: dict[str, JsonObject] = {}
    observations: list[JsonObject] = []
    for signal in signals:
        rows, total = _active_rows(fetch, signal)
        qualifying = sorted(
            (row for row in rows if str(row.get("verdict") or "").upper() in _QUALIFYING_VERDICTS),
            key=lambda row: str(row["symbol"]),
        )
        option_signal: bool | None = None
        signal_observations: list[JsonObject] = []
        for row in qualifying:
            observed = _observe_row(fetch, signal, row)
            if observed is None:
                option_signal = False
                break
            option_signal = True
            signal_observations.append(observed)
        per_signal[signal] = {
            "active_total": total,
            "qualifying_verdict_count": len(qualifying),
            # None: no qualifying row existed to prove whether the signal is optioned.
            "declares_option_structure": option_signal,
        }
        observations.extend(signal_observations)
    counts: dict[str, int] = {}
    for item in observations:
        counts[str(item["outcome"])] = counts.get(str(item["outcome"]), 0) + 1
    identity_payload = [
        (item["signal_id"], item["symbol"], item["observation_id"], item["outcome"])
        for item in observations
    ]
    checksum = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "artifact_version": "1.0.0",
        "sprint": "OPTIONS-PRODUCT-001",
        "ticket": "OP-07",
        "production_sha": production_sha,
        "captured_at": captured_at.astimezone(UTC).isoformat(),
        "signals": per_signal,
        "qualifying_option_results": len(observations),
        "outcome_counts": dict(sorted(counts.items())),
        "verdict": summarize(observations),
        "observation_checksum": checksum,
        "observations": observations,
    }


def http_fetcher(base_url: str, token: str, *, attempts: int = 3) -> Fetch:
    """Authenticated GET fetcher; transport failures on these idempotent reads retry."""
    normalized = base_url.rstrip("/")

    def fetch(path: str) -> FetchResponse:
        request = Request(
            normalized + path,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        for attempt in range(1, attempts + 1):
            try:
                with urlopen(request, timeout=30) as response:  # noqa: S310 - operator URL
                    return response.status, json.loads(response.read())
            except HTTPError as error:
                try:
                    body = json.loads(error.read())
                except ValueError:
                    body = {}
                return error.code, body if isinstance(body, dict) else {}
            except (URLError, HTTPException, TimeoutError, ConnectionError):
                if attempt == attempts:
                    raise
                sleep(2**attempt)
        raise AssertionError("unreachable")

    return fetch


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
    artifact = capture_founder_utility(
        http_fetcher(args.base_url, token),
        production_sha=args.production_sha,
        captured_at=datetime.now(UTC),
    )
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0 if artifact["verdict"] != "defect_reopen_correction" else 1


if __name__ == "__main__":
    raise SystemExit(main())
