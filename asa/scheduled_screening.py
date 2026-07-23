"""SPRINT-008D/PROD-002: scheduled production screening execution.

Calls screening.service.refresh() -- the same shared execution graph
POST /api/v1/screening/{signal}/{symbol}/refresh already calls, and that
screening/cli.py's own machinery underlies -- once per (signal, symbol)
pair in the production screening universe
(project/reports/SPRINT-008D-SCREENING-UNIVERSE.md), persisting through
the real PostgresScreeningStateRepository. No signal-selection or
acquisition logic is reimplemented here.

Not a background daemon: this module has no loop, no in-process scheduler,
no timer. It runs the full universe once per invocation and exits.
Scheduling -- how often this runs -- is deliberately kept external (a
Railway Cron Schedule or any equivalent externally-triggered invocation),
per this sprint's own architecture_principles.

Usage: python -m asa.scheduled_screening [--json]
Exit code: 0 if every pair completed without an unexpected exception (any
isolated per-signal failure outcome, e.g. missing data, is still a
completed, persisted result, not a failure of this runner); 1 if any
pair raised an exception this runner had to isolate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from asa.config import Settings
from asa.integrations.postgres import create_postgres_engine
from asa.integrations.screening_postgres import PostgresScreeningStateRepository
from market_data import load_market_data_config_from_environment
from market_data.live_transport import build_live_transport
from screening import APPROVED_LIVE_UNIVERSE, SIGNAL_REGISTRY
from screening.live_acquisition import (
    build_fulfillment_service_with_accounting,
    enabled_provider_configs,
    live_only_config,
)
from screening.service import refresh
from screening.state import ScreeningStateRepository

# The initial production screening universe
# (project/reports/SPRINT-008D-SCREENING-UNIVERSE.md, PROD-001): the two
# signals whose data requirements are met entirely by Tradier, across the
# full APPROVED_LIVE_UNIVERSE -- referenced directly, not copied, so this
# tuple can never silently drift out of sync with the one bound
# asa/api/screening_routes.py and screening/cli.py's own --live flag both
# already enforce (PROD-005 confirmed this explicitly). earnings_calendar
# is deliberately excluded pending PROD-004's own provider validation.
PRODUCTION_SCREENING_UNIVERSE: tuple[tuple[str, str], ...] = tuple(
    (signal_id, symbol)
    for signal_id in ("forward_factor", "skew_momentum")
    for symbol in APPROVED_LIVE_UNIVERSE
)


@dataclass(frozen=True, slots=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class PairOutcome:
    signal_id: str
    symbol: str
    outcome: str | None
    request_count: int | None
    error: str | None


def run_scheduled_refresh(
    universe: tuple[tuple[str, str], ...] = PRODUCTION_SCREENING_UNIVERSE,
    *,
    repository: ScreeningStateRepository | None = None,
    transport_factory: Callable[[str], object] = build_live_transport,
) -> tuple[PairOutcome, ...]:
    """Run one bounded refresh per pair in ``universe``, in order,
    persisting every result. One pair's failure never stops the others --
    a fresh CapabilityFulfillmentService (and its own request budget) is
    built per pair, exactly matching the per-request pattern
    asa/api/screening_routes.py already uses, never shared or cached
    across pairs.

    ``repository`` and ``transport_factory`` are injectable (default:
    the real Postgres repository and the real live transport) so this
    function is directly testable without a live database or network,
    the same DependencyOverrides-style pattern asa/bootstrap.py already
    uses.
    """
    resolved_repository = repository or PostgresScreeningStateRepository(
        create_postgres_engine(Settings().database_url)
    )
    config = live_only_config(load_market_data_config_from_environment())
    if not enabled_provider_configs(config):
        raise RuntimeError(
            "scheduled refresh requires at least one enabled live market data "
            "provider; none are enabled"
        )
    clock = _SystemClock()
    outcomes: list[PairOutcome] = []
    for signal_id, symbol in universe:
        fulfillment, budget_manager = build_fulfillment_service_with_accounting(
            config, transport_factory, clock
        )
        try:
            record = refresh(
                resolved_repository,
                SIGNAL_REGISTRY,
                fulfillment,
                clock,
                signal_id=signal_id,
                symbol=symbol,
            )
            outcomes.append(
                PairOutcome(
                    signal_id, symbol, record.outcome, len(budget_manager.accounting), None
                )
            )
        except Exception as exc:
            outcomes.append(PairOutcome(signal_id, symbol, None, None, str(exc)))
    return tuple(outcomes)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m asa.scheduled_screening",
        description="Run one bounded refresh per pair in the production screening universe.",
    )
    parser.add_argument("--json", action="store_true", help="Emit only machine-readable JSON.")
    args = parser.parse_args(argv)

    outcomes = run_scheduled_refresh()
    failures = [item for item in outcomes if item.error is not None]

    if not args.json:
        print(f"SCHEDULED SCREENING RUN -- {len(outcomes)} pairs")
        for item in outcomes:
            if item.error is not None:
                print(f"  {item.signal_id:<18} {item.symbol:<6} FAILED: {item.error}")
            else:
                print(
                    f"  {item.signal_id:<18} {item.symbol:<6} {item.outcome} "
                    f"(requests={item.request_count})"
                )

    print(
        json.dumps(
            {
                "total": len(outcomes),
                "failed": len(failures),
                "results": [
                    {
                        "signal_id": item.signal_id,
                        "symbol": item.symbol,
                        "outcome": item.outcome,
                        "request_count": item.request_count,
                        "error": item.error,
                    }
                    for item in outcomes
                ],
            }
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
