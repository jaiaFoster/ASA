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

from collections.abc import Mapping
from datetime import datetime

from domain import MarketCapability
from market_data import CapabilityRegistry
from market_data.capability_coalescing import reduce_option_chain_results
from market_data.fulfillment import CapabilityFulfillmentResult
from market_data.providers import CapabilityRequest
from market_data.resolution import ResolutionPolicy
from market_data.subject_plan import CapabilityFulfiller
from screening.subject_planning import CapabilityResultReducer
from strategies import (
    EARNINGS_CALENDAR_MANIFEST,
    FORWARD_FACTOR_CALENDAR_MANIFEST,
    SKEW_MOMENTUM_VERTICAL_MANIFEST,
)
from strategies.earnings_calendar_planning import earnings_calendar_resolved_field_requirements
from strategies.forward_factor_planning import (
    resolved_field_requirements as forward_factor_resolved_field_requirements,
)
from strategies.skew_momentum_planning import (
    resolved_field_requirements as skew_momentum_resolved_field_requirements,
)
from strategy_runtime.adapters.earnings_calendar import (
    EARNINGS_CALENDAR_CONTRACT,
    build_earnings_calendar_adapter,
)
from strategy_runtime.adapters.earnings_calendar_subject_first import (
    build_earnings_calendar_subject_preparation_binding,
)
from strategy_runtime.adapters.forward_factor import (
    FORWARD_FACTOR_CONTRACT,
    build_forward_factor_adapter,
)
from strategy_runtime.adapters.forward_factor_subject_first import (
    build_forward_factor_subject_preparation_binding,
)
from strategy_runtime.adapters.skew_momentum_subject_first import (
    build_skew_momentum_subject_preparation_binding,
)
from strategy_runtime.adapters.skew_momentum_vertical import (
    SKEW_MOMENTUM_VERTICAL_CONTRACT,
    build_skew_momentum_adapter,
)
from strategy_runtime.catalog import SignalCatalogEntry
from strategy_runtime.historical_evidence import HistoricalSkewRepository
from strategy_runtime.manifest_contract import validate_manifest_contract
from strategy_runtime.market_data_planning import resolution_policy_for_capabilities
from strategy_runtime.orchestration import CutoverPolicy
from strategy_runtime.registry import StrategyRegistry
from strategy_runtime.result import UniversalScreeningResult
from strategy_runtime.subject_preparation import SubjectPreparationRegistry

__all__ = [
    "EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR",
    "UNBOUND_FULFILLMENT",
    "build_migrated_cutover_policy",
    "build_migrated_shadow_registry",
    "build_migrated_signal_catalog",
    "build_migrated_strategy_registry",
    "migrated_shadow_capability_reducers",
    "migrated_shadow_resolution_policy",
]

EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR = "ASA_EARNINGS_CALENDAR_CUTOVER_ENABLED"


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


def build_migrated_shadow_registry(
    now: datetime, historical_skew_repository: HistoricalSkewRepository | None = None
) -> SubjectPreparationRegistry[object]:
    """Every migrated strategy with a registered subject-first shadow
    binding, assembled once per invocation/cycle (SPRINT-014 S14-PR-05A,
    Architect checkpoint: sixteenth review, "both roots must use the same
    new orchestration primitives"). Today, only Earnings Calendar has one;
    strategy_runtime.orchestration's own shared seam looks strategy_ids up
    here generically by registry membership, never by a hand-written
    if-branch -- a strategy with no entry here is simply never shadowed.

    Rebuilt fresh per caller invocation, never cached across cycles/
    requests, because build_earnings_calendar_subject_preparation_binding
    itself closes its own bootstrap demands and phase-two expansion over
    this exact ``now``.
    """
    return SubjectPreparationRegistry(
        (
            (
                FORWARD_FACTOR_CONTRACT.strategy_id,
                build_forward_factor_subject_preparation_binding(now),
            ),
            (
                SKEW_MOMENTUM_VERTICAL_CONTRACT.strategy_id,
                build_skew_momentum_subject_preparation_binding(
                    now, historical_skew_repository
                ),
            ),
            (
                EARNINGS_CALENDAR_CONTRACT.strategy_id,
                build_earnings_calendar_subject_preparation_binding(now),
            ),
        )
    )


def migrated_shadow_capability_reducers() -> dict[MarketCapability, CapabilityResultReducer]:
    """Generic multi-result capability reducers any registered shadow
    binding's own subject plan might need while sealing -- currently just
    OPTION_CHAIN_V1 (Earnings Calendar's own discovery-then-per-expiration-
    contract acquisition shape), forwarded unchanged into
    strategy_runtime.orchestration.prepare_subject_shadow_knowledge by
    both production roots.
    """
    return {MarketCapability.OPTION_CHAIN_V1: reduce_option_chain_results}


def migrated_shadow_resolution_policy(
    capability_registry: CapabilityRegistry,
) -> dict[MarketCapability, ResolutionPolicy]:
    """Resolution policies for every capability today's one registered
    shadow binding (Earnings Calendar) needs sealed, built from this
    subject's own already-built CapabilityRegistry -- never a second,
    hand-copied provider-priority list in asa/ (Architect checkpoint:
    fourteenth review, "provider metadata and resolution policies must be
    constructed from existing market-data configuration/registry
    ownership").
    """
    requirements = earnings_calendar_resolved_field_requirements()
    requirements.update(forward_factor_resolved_field_requirements())
    requirements.update(skew_momentum_resolved_field_requirements())
    return resolution_policy_for_capabilities(capability_registry, requirements)


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


def build_migrated_cutover_policy(values: Mapping[str, str]) -> CutoverPolicy:
    """The one shared cutover-policy owner both asa/scheduled_screening.py
    and asa/api/screening_routes.py call identically (SPRINT-014 S14-PR-05,
    Architect checkpoint: nineteenth review, "one shared cutover policy
    owner used identically by scheduled and API roots. Do not create
    separate route-specific switches").

    Reads ``ASA_EARNINGS_CALENDAR_CUTOVER_ENABLED`` from ``values`` (an
    explicit environment mapping, following
    market_data.config.load_market_data_config's own established
    boundary convention -- a caller passes os.environ at the actual
    process boundary, never read here directly). Only the migrated
    earnings_calendar strategy is ever eligible (Architect checkpoint:
    nineteenth review, "Scope it only to the migrated earnings_calendar
    strategy. FF/Skew stay on their existing legacy evaluation path.") --
    this function has no branch or parameter that could register any
    other strategy_id.

    Absent or falsy: earnings_calendar keeps its legacy-authoritative,
    shadow-compared rollback behavior. Truthy: earnings_calendar's own
    already-prepared subject-first knowledge becomes authoritative.
    Flipping this flag back is the entire rollback mechanism -- no data
    migration, since sealed subject-first evidence and attempt records
    already recorded are never touched by this function either way.
    """
    return CutoverPolicy(
        {
            FORWARD_FACTOR_CONTRACT.strategy_id: True,
            SKEW_MOMENTUM_VERTICAL_CONTRACT.strategy_id: True,
            EARNINGS_CALENDAR_CONTRACT.strategy_id: _boolean_flag(
                values, EARNINGS_CALENDAR_CUTOVER_ENABLED_VAR, default=True
            )
        }
    )


def _boolean_flag(values: Mapping[str, str], name: str, *, default: bool) -> bool:
    raw = values.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be boolean")
