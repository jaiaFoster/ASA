"""Migrated strategy adapters (SPRINT-009/EPIC-7).

One module per migrated strategy: forward_factor, skew_momentum_vertical,
earnings_calendar. Each declares its own StrategyContract (EPIC-2) and a
StrategyAdapter (EPIC-1) that reuses the existing, unmodified execution
graph (screening.live_adapters, strategies/stonk_manifests.py --
this sprint's own quality.preserve rule for "execution graph") and
translates its ScreeningResult into this sprint's UniversalScreeningResult
(EPIC-6) via _screening_bridge.translate_screening_result(), the one
translation rule every migrated strategy shares.

build_migrated_strategy_registry() (EPIC-9) is the one place all three
are actually registered together -- wiring that registry into the
deployed API's own route handlers remains a separate, deliberately
deferred step (see project/reports/SPRINT-009.md); importing this
subpackage has no side effect on the currently-shipped
/api/v1/screening* surface on its own.

SPRINT-014 S14-PR-05A (Architect checkpoint: twelfth review, item 3):
build_migrated_strategy_registry() now requires a CapabilityFulfiller,
closed over into all three adapters at construction time -- acquisition
is bound by closure, never read from RuntimeContext (which no longer
carries a fulfillment field). A caller that only needs this registry's
contract/membership metadata (e.g. asa/bootstrap.py's own
is_registered() checks, never actual evaluation) passes
UNBOUND_FULFILLMENT, which raises loudly if anything ever actually tries
to acquire data through it -- an explicit, visible placeholder, never a
silent empty-evidence fallback. A caller that is about to evaluate a
strategy for a real subject must rebuild this registry with that
subject's own real CapabilityFulfiller (raw or PlanBackedFulfillment)
immediately beforehand.
"""

from __future__ import annotations

from market_data.fulfillment import CapabilityFulfillmentResult
from market_data.providers import CapabilityRequest
from market_data.subject_plan import CapabilityFulfiller
from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
)
from strategy_runtime.adapters.earnings_calendar import (
    EARNINGS_CALENDAR_CONTRACT,
    build_earnings_calendar_adapter,
)
from strategy_runtime.adapters.forward_factor import (
    FORWARD_FACTOR_CONTRACT,
    build_forward_factor_adapter,
)
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
    build_skew_momentum_adapter,
)
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.manifest_contract import validate_manifest_contract
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult

__all__ = [
    "UNBOUND_FULFILLMENT",
    "build_migrated_signal_catalog",
    "build_migrated_strategy_registry",
]


class _UnboundFulfillment:
    """Placeholder CapabilityFulfiller for a registry built for contract/
    catalog metadata only -- raises immediately if anything ever actually
    tries to acquire data through it, rather than silently returning
    empty or fabricated evidence.
    """

    def fulfill(
        self, request: CapabilityRequest, *, required: bool = True
    ) -> CapabilityFulfillmentResult:
        raise RuntimeError(
            "this StrategyRegistry was built with UNBOUND_FULFILLMENT for contract/"
            "catalog metadata only -- rebuild it with a real subject-scoped "
            "CapabilityFulfiller before evaluating any strategy"
        )


UNBOUND_FULFILLMENT = _UnboundFulfillment()


def build_migrated_strategy_registry(
    fulfillment: CapabilityFulfiller,
) -> StrategyRegistry[UniversalScreeningResult]:
    """All three EPIC-7 migration targets, registered together -- the one
    place this sprint's own "three production strategies execute through
    one shared runtime" success criterion is assembled and directly
    checkable (see tests/strategy_runtime/adapters/test_registry.py).

    ``fulfillment`` is closed over into all three adapters -- pass
    UNBOUND_FULFILLMENT for a registry that is only ever used for
    contract/membership metadata, or a real CapabilityFulfiller
    (typically one subject's own PlanBackedFulfillment) immediately
    before evaluating that subject.
    """
    pairs = (
        (FORWARD_FACTOR_CALENDAR_MANIFEST, FORWARD_FACTOR_CONTRACT),
        (SKEW_MOMENTUM_VERTICAL_MANIFEST, SKEW_MOMENTUM_VERTICAL_CONTRACT),
        (EARNINGS_CALENDAR_MANIFEST, EARNINGS_CALENDAR_CONTRACT),
    )
    for manifest, contract in pairs:
        validate_manifest_contract(manifest, contract)
    return StrategyRegistry(
        (
            (FORWARD_FACTOR_CONTRACT, build_forward_factor_adapter(fulfillment)),
            (SKEW_MOMENTUM_VERTICAL_CONTRACT, build_skew_momentum_adapter(fulfillment)),
            (EARNINGS_CALENDAR_CONTRACT, build_earnings_calendar_adapter(fulfillment)),
        )
    )


def build_migrated_signal_catalog() -> tuple[SignalCatalogEntry, ...]:
    """Public capability metadata projected from the universal contracts."""
    entries = (
        SignalCatalogEntry.from_contract(
            EARNINGS_CALENDAR_CONTRACT,
            manifest_id=EARNINGS_CALENDAR_MANIFEST.manifest_id,
        ),
        SignalCatalogEntry.from_contract(
            FORWARD_FACTOR_CONTRACT,
            manifest_id=FORWARD_FACTOR_CALENDAR_MANIFEST.manifest_id,
        ),
        SignalCatalogEntry.from_contract(
            SKEW_MOMENTUM_VERTICAL_CONTRACT,
            manifest_id=SKEW_MOMENTUM_VERTICAL_MANIFEST.manifest_id,
        ),
    )
    return tuple(sorted(entries, key=lambda item: item.signal_id))
