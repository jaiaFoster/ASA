"""Typed, deterministic strategy data requirement projections (SPRINT-014
S14-PR-02).

A requirement projection reads a strategy's own manifest -- the single
canonical authority for its parameters (ADR-010) -- and produces a typed,
frozen description of what evidence that strategy needs. It performs no
provider call, no acquisition, no I/O of any kind: every value here already
exists in the manifest, this module only gives it a typed, queryable shape
instead of a hand-duplicated copy.

This directly resolves SPRINT-013 S13-08's audit finding #1
(project/reports/SPRINT-013-S13-08-audit.md): Earnings Calendar's DTE
selection policy was duplicated between screening/live_adapters.py's own
hardcoded dict and strategies/stonk_manifests.py's expiration_select node
parameters, with no accessor to read the manifest's own copy instead of
re-typing it. screening/live_adapters.py now sources its policy from
earnings_calendar_requirement() below; the manifest is the only owner.

Scope (SPRINT-014 S14-PR-02): Earnings Calendar only, per this ticket's own
migration_strategy. A future ticket may generalize this pattern to other
strategies once a second consumer proves the shape is actually reusable
(SPRINT-013's own "extract only after semantic identity is proven" rule).
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import MarketCapability
from strategies.manifest import StrategyManifest, node_parameter_value
from strategies.stonk_manifests import EARNINGS_CALENDAR_MANIFEST


@dataclass(frozen=True, slots=True)
class EarningsCalendarExpirationPolicy:
    """Earnings Calendar's own front/back expiration-pair selection policy,
    read from its manifest's expiration_select node -- never a second,
    independently maintained copy.
    """

    front_min_dte: int
    front_max_dte: int
    back_min_dte: int
    back_max_dte: int
    target_gap_days: int
    gap_tolerance_days: int


@dataclass(frozen=True, slots=True)
class EarningsCalendarRequirement:
    """Complete typed data requirement for one Earnings Calendar
    evaluation: which market capabilities it needs and the expiration
    policy governing which contracts within those capabilities are
    selected. Acquisition planning (SPRINT-014 S14-PR-03) consumes this;
    it never constructs its own copy of these values.
    """

    capabilities: tuple[MarketCapability, ...]
    expiration_policy: EarningsCalendarExpirationPolicy
    lookahead_days: int


def _int_parameter(manifest: StrategyManifest, node_id: str, parameter_name: str) -> int:
    value = node_parameter_value(manifest, node_id, parameter_name)
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def earnings_calendar_requirement(
    manifest: StrategyManifest = EARNINGS_CALENDAR_MANIFEST,
) -> EarningsCalendarRequirement:
    """Project Earnings Calendar's typed data requirement from its own
    manifest. Deterministic and order-independent: depends only on the
    manifest's own already-canonically-ordered content, never on wall
    clock, randomness, or call order. Performs no provider call.
    """
    capabilities = tuple(
        MarketCapability(item.name) for item in manifest.required_market_capabilities
    )
    expiration_policy = EarningsCalendarExpirationPolicy(
        front_min_dte=_int_parameter(manifest, "expiration_select", "front_min_dte"),
        front_max_dte=_int_parameter(manifest, "expiration_select", "front_max_dte"),
        back_min_dte=_int_parameter(manifest, "expiration_select", "back_min_dte"),
        back_max_dte=_int_parameter(manifest, "expiration_select", "back_max_dte"),
        target_gap_days=_int_parameter(manifest, "expiration_select", "target_gap_days"),
        gap_tolerance_days=_int_parameter(manifest, "expiration_select", "gap_tolerance_days"),
    )
    return EarningsCalendarRequirement(
        capabilities=capabilities,
        expiration_policy=expiration_policy,
        lookahead_days=expiration_policy.back_max_dte,
    )
