"""Bounded, deterministic screening entrypoint (SCREEN-005).

    python -m screening [--strategies ID[,ID...]] [--universe SYMBOL[,...]]
                         [--as-of ISO8601] [--dry-run] [--live] [--json]

Exit codes: 0 for a completed orchestration run -- regardless of individual
strategy outcomes (PASS/NO_SIGNAL/MISSING_DATA/MALFORMED_OUTPUT/
STRATEGY_EXCEPTION are all isolated per-strategy results, not orchestration
failures); 2 for an orchestration-level failure (unknown strategy_id,
unsupported universe symbol, a malformed --as-of value, or --live -- not yet
available, deferred to a successor sprint).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from dataclasses import dataclass

from screening.adapters import TARGET_STRATEGY_ADAPTERS, TARGET_STRATEGY_REGISTRY
from screening.errors import UnknownScreeningStrategyIdError
from screening.fixtures import SAFE_SYMBOL
from screening.registry import ScreeningStrategyDefinition
from screening.results import ScreeningResult
from screening.runner import run_screening
from screening.serialization import results_to_json_payload

APPROVED_FIXTURE_UNIVERSE = (SAFE_SYMBOL,)

_ORCHESTRATION_FAILURE_EXIT_CODE = 2


@dataclass(frozen=True)
class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class FixedClock:
    fixed_at: datetime

    def now(self) -> datetime:
        return self.fixed_at


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m screening",
        description=(
            "Bounded, deterministic screening entrypoint for ready target strategies "
            "(forward_factor, earnings_calendar, skew_momentum)."
        ),
    )
    parser.add_argument(
        "--strategies",
        default=None,
        help="Comma-separated strategy_ids to run (default: all registered).",
    )
    parser.add_argument(
        "--universe",
        default=",".join(APPROVED_FIXTURE_UNIVERSE),
        help=(
            "Comma-separated symbol universe. Only the approved fixture universe "
            f"({', '.join(APPROVED_FIXTURE_UNIVERSE)}) is supported this sprint -- "
            "live, arbitrary universes are deferred to a successor sprint."
        ),
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Timezone-aware ISO8601 timestamp for the run clock (default: current time).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan mode: show which strategies and canonical capabilities would run, "
        "without executing any strategy.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Bounded live acquisition. NOT YET AVAILABLE this sprint -- deferred to "
        "SPRINT-007; passing this flag fails closed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit only the machine-readable JSON payload (suppresses the human summary).",
    )
    return parser


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _print_dry_run_summary(plan: Sequence[ScreeningStrategyDefinition]) -> None:
    print("DRY RUN -- plan only, no strategy was executed.")
    for entry in plan:
        capabilities = ", ".join(capability.value for capability in entry.required_capabilities)
        print(f"  would run: {entry.strategy_id} (capabilities: {capabilities})")


def _print_results_summary(results: Sequence[ScreeningResult]) -> None:
    print("SCREENING RUN")
    for result in results:
        print(
            f"  {result.strategy_id:<18} {result.outcome_status.value:<18} "
            f"classification={result.signal_classification!r} "
            f"score={result.strategy_native_score!r}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.live:
        print(
            "error: --live is not yet available. Live acquisition is explicitly deferred "
            "to a successor sprint (SPRINT-007); this sprint's screening runs are "
            "fixture-backed only.",
            file=sys.stderr,
        )
        return _ORCHESTRATION_FAILURE_EXIT_CODE

    requested_universe = _parse_csv(args.universe)
    unsupported = set(requested_universe) - set(APPROVED_FIXTURE_UNIVERSE)
    if not requested_universe or unsupported:
        print(
            f"error: unsupported universe symbol(s) {sorted(unsupported) or list(requested_universe)}. "
            f"Only {APPROVED_FIXTURE_UNIVERSE} is supported this sprint.",
            file=sys.stderr,
        )
        return _ORCHESTRATION_FAILURE_EXIT_CODE

    requested_strategy_ids: tuple[str, ...] | None
    if args.strategies is None:
        requested_strategy_ids = None
    else:
        requested_strategy_ids = _parse_csv(args.strategies)
        unknown = set(requested_strategy_ids) - set(TARGET_STRATEGY_REGISTRY.registered_ids())
        if not requested_strategy_ids or unknown:
            print(
                f"error: unknown strategy_id(s) {sorted(unknown) or list(requested_strategy_ids)}. "
                f"Registered: {TARGET_STRATEGY_REGISTRY.registered_ids()}.",
                file=sys.stderr,
            )
            return _ORCHESTRATION_FAILURE_EXIT_CODE

    if args.as_of is None:
        clock: SystemClock | FixedClock = SystemClock()
    else:
        try:
            parsed = datetime.fromisoformat(args.as_of)
        except ValueError:
            print(f"error: --as-of is not a valid ISO8601 timestamp: {args.as_of!r}", file=sys.stderr)
            return _ORCHESTRATION_FAILURE_EXIT_CODE
        if parsed.tzinfo is None:
            print("error: --as-of must be timezone-aware", file=sys.stderr)
            return _ORCHESTRATION_FAILURE_EXIT_CODE
        clock = FixedClock(parsed)

    effective_ids = requested_strategy_ids or TARGET_STRATEGY_REGISTRY.registered_ids()

    if args.dry_run:
        plan = [TARGET_STRATEGY_REGISTRY.get(strategy_id) for strategy_id in sorted(effective_ids)]
        if not args.json:
            _print_dry_run_summary(plan)
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "as_of": clock.now().isoformat(),
                    "plan": [
                        {
                            "strategy_id": entry.strategy_id,
                            "strategy_version": entry.strategy_version,
                            "required_capabilities": [c.value for c in entry.required_capabilities],
                        }
                        for entry in plan
                    ],
                }
            )
        )
        return 0

    try:
        results = run_screening(
            TARGET_STRATEGY_REGISTRY,
            TARGET_STRATEGY_ADAPTERS,
            clock,
            strategy_ids=requested_strategy_ids,
        )
    except UnknownScreeningStrategyIdError as exc:
        print(f"error: orchestration failure: {exc}", file=sys.stderr)
        return _ORCHESTRATION_FAILURE_EXIT_CODE

    if not args.json:
        _print_results_summary(results)
    print(json.dumps(results_to_json_payload(results, dry_run=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
