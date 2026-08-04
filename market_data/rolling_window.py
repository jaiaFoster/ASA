"""Shared, cross-pair provider rolling-window request tracking (SPRINT-013
S13-03A).

RequestBudgetManager (market_data/budget.py) is deliberately rebuilt fresh
per pair -- one pair's local accounting, retries, and burst behavior must
never leak into another's. A provider's real external rate limit is the
opposite: a property of the provider, not of any one pair, so it cannot be
enforced correctly by a per-pair-scoped ledger no matter how it's fixed.
ProviderRollingWindowTracker is the one deliberately shared, cross-pair
piece of state in the whole acquisition path -- minted once per screening
cycle (never per pair) and consulted, not owned, by each pair's
RequestBudgetManager.

Window durations and limits are never invented here -- they are sourced
from each provider's own declared, documented limits
(market_data.providers.ProviderLimitDeclaration) at composition time,
outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from domain.values import DomainInvariantError, require_tz_aware
from market_data.factory import Clock


@dataclass(frozen=True, slots=True)
class RollingWindowPolicy:
    """One provider's real, documented rolling rate limit."""

    provider_id: str
    window_seconds: int
    window_limit: int
    source: str

    def __post_init__(self) -> None:
        if not self.provider_id or self.provider_id != self.provider_id.strip():
            raise DomainInvariantError("RollingWindowPolicy.provider_id must be normalized")
        if type(self.window_seconds) is not int or self.window_seconds <= 0:
            raise DomainInvariantError("RollingWindowPolicy.window_seconds must be positive")
        if type(self.window_limit) is not int or self.window_limit <= 0:
            raise DomainInvariantError("RollingWindowPolicy.window_limit must be positive")
        if not self.source or self.source != self.source.strip():
            raise DomainInvariantError("RollingWindowPolicy.source must be normalized")


class ProviderRollingWindowTracker:
    """One instance per screening cycle, shared across every pair.

    try_reserve() is a genuine monotonic sliding window: each provider
    keeps a deque of its own recent reservation timestamps, pruned to
    ``window_seconds`` on every call, so it correctly aggregates real
    concurrent/near-concurrent requests from different pairs -- unlike
    RequestBudgetManager's old per-pair burst bug, which keyed usage by
    exact timestamp and so never aggregated anything in production.

    A provider with no configured RollingWindowPolicy is always allowed
    (this tracker adds protection, it never invents a limit that wasn't
    declared).
    """

    __slots__ = ("_policies", "_clock", "_reservations", "_reset_until")

    def __init__(self, policies: tuple[RollingWindowPolicy, ...], clock: Clock) -> None:
        provider_ids = tuple(item.provider_id for item in policies)
        if len(provider_ids) != len(set(provider_ids)):
            raise DomainInvariantError("RollingWindowPolicy provider_id values must be unique")
        self._policies = {item.provider_id: item for item in policies}
        self._clock = clock
        self._reservations: dict[str, list[datetime]] = {}
        self._reset_until: dict[str, datetime] = {}

    def try_reserve(self, provider_id: str) -> bool:
        policy = self._policies.get(provider_id)
        if policy is None:
            return True
        now = self._clock.now()
        require_tz_aware(now, "ProviderRollingWindowTracker", "clock")
        reset_until = self._reset_until.get(provider_id)
        if reset_until is not None and now < reset_until:
            return False
        window_start = now - timedelta(seconds=policy.window_seconds)
        recent = [
            value for value in self._reservations.get(provider_id, []) if value > window_start
        ]
        if len(recent) >= policy.window_limit:
            self._reservations[provider_id] = recent
            return False
        recent.append(now)
        self._reservations[provider_id] = recent
        return True

    def apply_reset_hint(self, provider_id: str, resets_at: datetime) -> None:
        """Safe application of a provider-reported reset/quota hint: may
        only SHORTEN local allowance (treat the provider as exhausted
        until ``resets_at``), never lengthen it or grant additional
        requests beyond the configured window_limit. A hint for a
        provider with no configured policy is ignored -- there is nothing
        to safely tighten.
        """
        if provider_id not in self._policies:
            return
        require_tz_aware(resets_at, "ProviderRollingWindowTracker", "resets_at")
        current = self._reset_until.get(provider_id)
        if current is None or resets_at > current:
            self._reset_until[provider_id] = resets_at

    def summary(self) -> dict[str, int]:
        """Sanitized, cycle-level accounting: current in-window reservation
        count per configured provider. No payloads, headers, or
        credentials -- provider_id and an integer count only.
        """
        now = self._clock.now()
        result: dict[str, int] = {}
        for provider_id, policy in self._policies.items():
            window_start = now - timedelta(seconds=policy.window_seconds)
            result[provider_id] = sum(
                1 for value in self._reservations.get(provider_id, []) if value > window_start
            )
        return result
