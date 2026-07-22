"""Bounded request authorization and immutable accounting records (MD-006)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from domain import MarketCapability
from domain.values import DomainInvariantError, require_tz_aware
from market_data.factory import Clock
from market_data.providers import RequestBudgetAuthorization


class BudgetExhaustedError(RuntimeError):
    """A request was refused before transport because its explicit budget was exhausted."""


class BudgetScope(str, Enum):
    RUNTIME = "runtime"
    VALIDATION = "validation"


class RequestOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class RequestBudgetPolicy:
    provider_id: str
    scope: BudgetScope
    maximum_request_units: int
    burst_limit: int
    maximum_retries_per_request: int
    policy_version: str

    def __post_init__(self) -> None:
        for name in ("provider_id", "policy_version"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise DomainInvariantError(f"RequestBudgetPolicy.{name} must be normalized")
        for name in ("maximum_request_units", "burst_limit"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise DomainInvariantError(f"RequestBudgetPolicy.{name} must be positive")
        if self.burst_limit > self.maximum_request_units:
            raise DomainInvariantError("RequestBudgetPolicy burst exceeds total budget")
        if (
            type(self.maximum_retries_per_request) is not int
            or self.maximum_retries_per_request < 0
        ):
            raise DomainInvariantError("RequestBudgetPolicy retries must be non-negative")


@dataclass(frozen=True, slots=True)
class QuotaObservation:
    provider_id: str
    observed_at: datetime
    remaining: int | None
    limit: int | None
    resets_at: datetime | None
    source_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        require_tz_aware(self.observed_at, "QuotaObservation", "observed_at")
        if self.resets_at is not None:
            require_tz_aware(self.resets_at, "QuotaObservation", "resets_at")
        for name in ("remaining", "limit"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise DomainInvariantError(f"QuotaObservation.{name} must be non-negative")
        if self.remaining is not None and self.limit is not None and self.remaining > self.limit:
            raise DomainInvariantError("QuotaObservation remaining exceeds limit")
        fields = tuple(sorted(set(self.source_fields)))
        if not fields:
            raise DomainInvariantError("QuotaObservation requires source field names")
        object.__setattr__(self, "source_fields", fields)


@dataclass(frozen=True, slots=True)
class RequestAccountingEntry:
    authorization_id: str
    retry_root_id: str
    provider_id: str
    capability: MarketCapability
    scope: BudgetScope
    request_units: int
    attempt_number: int
    authorized_at: datetime
    outcome: RequestOutcome | None
    completed_at: datetime | None
    quota: QuotaObservation | None

    def __post_init__(self) -> None:
        require_tz_aware(self.authorized_at, "RequestAccountingEntry", "authorized_at")
        if not self.authorization_id or not self.retry_root_id:
            raise DomainInvariantError("RequestAccountingEntry identities must be non-empty")
        if type(self.request_units) is not int or self.request_units <= 0:
            raise DomainInvariantError("RequestAccountingEntry.request_units must be positive")
        if type(self.attempt_number) is not int or self.attempt_number <= 0:
            raise DomainInvariantError("RequestAccountingEntry.attempt_number must be positive")
        if (self.outcome is None) != (self.completed_at is None):
            raise DomainInvariantError("RequestAccountingEntry completion is inconsistent")
        if self.completed_at is not None:
            require_tz_aware(self.completed_at, "RequestAccountingEntry", "completed_at")
            if self.completed_at < self.authorized_at:
                raise DomainInvariantError("Request accounting completion precedes authorization")


class RequestBudgetManager:
    """Explicit per-run operational ledger; no background retries or hidden provider state."""

    __slots__ = ("_policies", "_clock", "_entries", "_cooldowns", "_burst")

    def __init__(self, policies: tuple[RequestBudgetPolicy, ...], clock: Clock) -> None:
        ordered = tuple(sorted(policies, key=lambda value: (value.provider_id, value.scope.value)))
        keys = tuple((value.provider_id, value.scope) for value in ordered)
        if not ordered or len(keys) != len(set(keys)):
            raise DomainInvariantError("Request budgets must be non-empty and unique")
        self._policies = ordered
        self._clock = clock
        self._entries: list[RequestAccountingEntry] = []
        self._cooldowns: dict[str, datetime] = {}
        self._burst: dict[tuple[str, BudgetScope, datetime], int] = {}

    @property
    def accounting(self) -> tuple[RequestAccountingEntry, ...]:
        return tuple(self._entries)

    def _policy(self, provider_id: str, scope: BudgetScope) -> RequestBudgetPolicy:
        matches = tuple(
            value
            for value in self._policies
            if value.provider_id == provider_id and value.scope is scope
        )
        if len(matches) != 1:
            raise BudgetExhaustedError(
                f"No finite {scope.value} request budget for provider {provider_id!r}"
            )
        return matches[0]

    def authorize(
        self,
        provider_id: str,
        capability: MarketCapability,
        request_units: int,
        scope: BudgetScope = BudgetScope.RUNTIME,
        *,
        retry_of: str | None = None,
    ) -> RequestBudgetAuthorization:
        if type(request_units) is not int or request_units <= 0:
            raise BudgetExhaustedError("Request units must be a positive integer")
        policy = self._policy(provider_id, scope)
        now = self._clock.now()
        require_tz_aware(now, "RequestBudgetManager", "clock")
        cooldown = self._cooldowns.get(provider_id)
        if cooldown is not None and now < cooldown:
            raise BudgetExhaustedError(f"Provider {provider_id!r} is in explicit cooldown")
        consumed = sum(
            value.request_units
            for value in self._entries
            if value.provider_id == provider_id and value.scope is scope
        )
        if consumed + request_units > policy.maximum_request_units:
            raise BudgetExhaustedError(f"Provider {provider_id!r} {scope.value} budget exhausted")
        burst_key = (provider_id, scope, now)
        burst = self._burst.get(burst_key, 0)
        if burst + 1 > policy.burst_limit:
            raise BudgetExhaustedError(f"Provider {provider_id!r} burst budget exhausted")
        attempt_number = 1
        retry_root_id: str | None = None
        if retry_of is not None:
            original = tuple(value for value in self._entries if value.authorization_id == retry_of)
            if len(original) != 1 or original[0].provider_id != provider_id:
                raise BudgetExhaustedError("Retry references an unknown authorization")
            retry_root_id = original[0].retry_root_id
            retries = sum(
                1
                for value in self._entries
                if value.retry_root_id == retry_root_id and value.attempt_number > 1
            )
            if retries >= policy.maximum_retries_per_request:
                raise BudgetExhaustedError(f"Provider {provider_id!r} retry budget exhausted")
            attempt_number = original[0].attempt_number + 1
        sequence = len(self._entries) + 1
        payload = json.dumps(
            {
                "capability": capability.value,
                "provider_id": provider_id,
                "request_units": request_units,
                "scope": scope.value,
                "sequence": sequence,
                "time": now.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        authorization_id = hashlib.sha256(payload).hexdigest()
        if retry_root_id is None:
            retry_root_id = authorization_id
        self._entries.append(
            RequestAccountingEntry(
                authorization_id,
                retry_root_id,
                provider_id,
                capability,
                scope,
                request_units,
                attempt_number,
                now,
                None,
                None,
                None,
            )
        )
        self._burst[burst_key] = burst + 1
        return RequestBudgetAuthorization(
            authorization_id,
            provider_id,
            request_units,
            policy.maximum_retries_per_request + 1,
        )

    def complete(
        self,
        authorization_id: str,
        outcome: RequestOutcome,
        *,
        quota: QuotaObservation | None = None,
        retry_after_seconds: int | None = None,
    ) -> RequestAccountingEntry:
        matches = [index for index, value in enumerate(self._entries) if value.authorization_id == authorization_id]
        if len(matches) != 1:
            raise DomainInvariantError("Unknown request authorization")
        index = matches[0]
        current = self._entries[index]
        if current.outcome is not None:
            raise DomainInvariantError("Request authorization is already completed")
        now = self._clock.now()
        if retry_after_seconds is not None:
            if type(retry_after_seconds) is not int or retry_after_seconds < 0:
                raise DomainInvariantError("retry_after_seconds must be non-negative")
            self._cooldowns[current.provider_id] = now + timedelta(seconds=retry_after_seconds)
        completed = RequestAccountingEntry(
            current.authorization_id,
            current.retry_root_id,
            current.provider_id,
            current.capability,
            current.scope,
            current.request_units,
            current.attempt_number,
            current.authorized_at,
            outcome,
            now,
            quota,
        )
        self._entries[index] = completed
        return completed
