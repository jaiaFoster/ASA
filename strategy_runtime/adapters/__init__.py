"""Migrated strategy adapters (SPRINT-009/EPIC-7, revised by SPRINT-014
S14-PR-05).

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

## Legacy fulfillment composition binding (SPRINT-014 S14-PR-05)

RuntimeContext no longer carries a fulfillment object (I-09). Earnings
Calendar is migrated to the subject-first evidence path
(RuntimeContext.sealed_evidence) and its adapter takes no fulfillment
parameter at all. Forward Factor and Skew Momentum have not yet been
migrated -- their adapter functions each take an explicit second
``fulfillment: CapabilityFulfillmentService | None`` parameter, and
build_migrated_strategy_registry() closes over
``legacy_fulfillment_by_subject`` to supply it, entirely outside
RuntimeContext. StrategyRegistry's own adapter type
(strategy_runtime.registry.StrategyAdapter) is single-argument
(Callable[[RuntimeContext], TResult]); the two wrapper closures below are
what StrategyRegistry actually holds, matching that type exactly, while
each legacy strategy's own module keeps its real two-argument signature.

Owner: SPRINT-014 Worker (delegate under GOV-AMD-001 Amendment 013).
Deletion condition: delete ``legacy_fulfillment_by_subject``, the two
wrapper closures, and forward_factor_adapter's/skew_momentum_adapter's own
``fulfillment`` parameter the moment each strategy is itself migrated to
the subject-first path (tracked as follow-on tickets after this sprint
closes) -- not before, and not incidentally as part of an unrelated change.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from market_data import CapabilityFulfillmentService
from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
)
from strategy_runtime.adapters.earnings_calendar import (
    EARNINGS_CALENDAR_CONTRACT,
    earnings_calendar_adapter,
    legacy_earnings_calendar_adapter,
)
from strategy_runtime.adapters.forward_factor import (
    FORWARD_FACTOR_CONTRACT,
    forward_factor_adapter,
)
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
    skew_momentum_adapter,
)
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.context import RuntimeContext
from strategy_runtime.manifest_contract import validate_manifest_contract
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult

__all__ = ["build_migrated_signal_catalog", "build_migrated_strategy_registry"]

_NO_LEGACY_FULFILLMENT: Mapping[str, CapabilityFulfillmentService] = MappingProxyType({})


def build_migrated_strategy_registry(
    *,
    legacy_fulfillment_by_subject: Mapping[
        str, CapabilityFulfillmentService
    ] = _NO_LEGACY_FULFILLMENT,
    earnings_calendar_cutover_enabled: bool = True,
) -> StrategyRegistry[UniversalScreeningResult]:
    """All three EPIC-7 migration targets, registered together -- the one
    place this sprint's own "three production strategies execute through
    one shared runtime" success criterion is assembled and directly
    checkable (see tests/strategy_runtime/adapters/test_registry.py).

    ``legacy_fulfillment_by_subject`` (SPRINT-014 S14-PR-05, see this
    module's own docstring) supplies Forward Factor's and Skew Momentum's
    own fulfillment service, captured by closure at registry-construction
    time -- never through RuntimeContext. Earnings Calendar's own adapter
    reads no fulfillment at all, legacy or otherwise -- UNLESS
    ``earnings_calendar_cutover_enabled=False`` (S14-PR-05's own required
    rollback switch), in which case Earnings Calendar is registered
    against legacy_earnings_calendar_adapter instead, reusing the same
    legacy_fulfillment_by_subject binding FF/SM already use. Restores only
    the old Earnings Calendar path -- it never deletes or bypasses any
    already-sealed evidence a caller separately acquired this cycle.
    """
    pairs = (
        (FORWARD_FACTOR_CALENDAR_MANIFEST, FORWARD_FACTOR_CONTRACT),
        (SKEW_MOMENTUM_VERTICAL_MANIFEST, SKEW_MOMENTUM_VERTICAL_CONTRACT),
        (EARNINGS_CALENDAR_MANIFEST, EARNINGS_CALENDAR_CONTRACT),
    )
    for manifest, contract in pairs:
        validate_manifest_contract(manifest, contract)

    def _forward_factor_legacy_binding(context: RuntimeContext) -> UniversalScreeningResult:
        return forward_factor_adapter(context, legacy_fulfillment_by_subject.get(context.subject))

    def _skew_momentum_legacy_binding(context: RuntimeContext) -> UniversalScreeningResult:
        return skew_momentum_adapter(context, legacy_fulfillment_by_subject.get(context.subject))

    def _earnings_calendar_legacy_binding(context: RuntimeContext) -> UniversalScreeningResult:
        return legacy_earnings_calendar_adapter(
            context, legacy_fulfillment_by_subject.get(context.subject)
        )

    earnings_calendar_binding = (
        earnings_calendar_adapter
        if earnings_calendar_cutover_enabled
        else _earnings_calendar_legacy_binding
    )
    return StrategyRegistry(
        (
            (FORWARD_FACTOR_CONTRACT, _forward_factor_legacy_binding),
            (SKEW_MOMENTUM_VERTICAL_CONTRACT, _skew_momentum_legacy_binding),
            (EARNINGS_CALENDAR_CONTRACT, earnings_calendar_binding),
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
