"""Bounded, deterministic screening entrypoint (SCREEN-005, LIVE-002).

    python -m screening [--strategies ID[,ID...]] [--universe SYMBOL[,...]]
                         [--as-of ISO8601] [--dry-run] [--live] [--json]

Exit codes: 0 for a completed orchestration run -- regardless of individual
strategy outcomes (PASS/NO_SIGNAL/MISSING_DATA/MALFORMED_OUTPUT/
STRATEGY_EXCEPTION are all isolated per-strategy results, not orchestration
failures); 2 for an orchestration-level failure (unknown strategy_id,
unsupported universe symbol, a malformed --as-of value).

--live runs against real, network-connected providers (per
market_data.load_market_data_config_from_environment()'s configured, enabled
providers) instead of the offline deterministic fixture, one symbol at a
time across the requested universe. Without --live, --universe stays bounded
to APPROVED_FIXTURE_UNIVERSE (SAFE_SYMBOL only); with --live, it accepts
APPROVED_LIVE_UNIVERSE -- the SPRINT-007 validation_universe (AAPL, MSFT,
NVDA, AMD, SPY, QQQ). Actually exercising this against real provider
credentials for the first time is LIVE-003's explicitly Founder-gated
concern, not this flag's -- this flag only makes the capability real.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from dataclasses import dataclass, replace

from market_data import MarketDataConfig, load_market_data_config_from_environment
from market_data.live_transport import build_live_transport
from screening.adapters import TARGET_STRATEGY_ADAPTERS, TARGET_STRATEGY_REGISTRY
from screening.errors import UnknownScreeningStrategyIdError
from screening.fixtures import SAFE_SYMBOL
from screening.live_acquisition import build_fulfillment_service, enabled_provider_configs
from screening.live_adapters import build_live_adapters
from screening.registry import ScreeningStrategyDefinition
from screening.results import ScreeningResult
from screening.runner import run_screening
from screening.serialization import results_to_json_payload

APPROVED_FIXTURE_UNIVERSE = (SAFE_SYMBOL,)
APPROVED_LIVE_UNIVERSE = ("AAPL", "MSFT", "NVDA", "AMD", "SPY", "QQQ")

_ORCHESTRATION_FAILURE_EXIT_CODE = 2
_FIXTURE_PROVIDER_ID = "deterministic_fixture"


def _live_only_config(config: MarketDataConfig) -> MarketDataConfig:
    """deterministic_fixture defaults to enabled (market_data/config.py's own
    safety default) and, being alphabetically first among enabled providers,
    would otherwise be tried before any real provider by
    CapabilityRegistry's deterministic priority order -- silently serving
    every --live request from offline fixture data instead of a real
    provider. --live must mean live, so the fixture provider is always
    force-disabled here, regardless of environment configuration.
    """
    providers = tuple(
        replace(item, enabled=False) if item.provider_id == _FIXTURE_PROVIDER_ID else item
        for item in config.providers
    )
    return replace(config, providers=providers)


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
        default=None,
        help=(
            "Comma-separated symbol universe. Without --live: the approved fixture "
            f"universe ({', '.join(APPROVED_FIXTURE_UNIVERSE)}). With --live: the "
            f"approved live validation universe ({', '.join(APPROVED_LIVE_UNIVERSE)}). "
            "Arbitrary, unbounded universes are not supported."
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
        help="Bounded live acquisition against real, network-connected providers "
        f"for the approved live universe ({', '.join(APPROVED_LIVE_UNIVERSE)}), "
        "instead of the offline fixture.",
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

    approved_universe = APPROVED_LIVE_UNIVERSE if args.live else APPROVED_FIXTURE_UNIVERSE
    universe_arg = args.universe if args.universe is not None else ",".join(approved_universe)
    requested_universe = _parse_csv(universe_arg)
    unsupported = set(requested_universe) - set(approved_universe)
    if not requested_universe or unsupported:
        print(
            f"error: unsupported universe symbol(s) {sorted(unsupported) or list(requested_universe)}. "
            f"Only {approved_universe} is supported "
            f"{'in --live mode' if args.live else 'without --live'}.",
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
        if args.live:
            config = _live_only_config(load_market_data_config_from_environment())
            if not enabled_provider_configs(config):
                print(
                    "error: --live requires at least one enabled live provider "
                    "(tradier, finnhub, or alpha_vantage) configured via environment "
                    "variables -- none are enabled.",
                    file=sys.stderr,
                )
                return _ORCHESTRATION_FAILURE_EXIT_CODE
            fulfillment = build_fulfillment_service(config, build_live_transport, clock)
            results = tuple(
                result
                for symbol in requested_universe
                for result in run_screening(
                    TARGET_STRATEGY_REGISTRY,
                    build_live_adapters(symbol, fulfillment),
                    clock,
                    strategy_ids=requested_strategy_ids,
                )
            )
        else:
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
