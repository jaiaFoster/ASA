"""Immutable, self-contained Market Snapshot construction (MD-014)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import cast
from domain import EvidenceReference, MarketCapability, MarketObservation
from domain.values import DomainInvariantError, require_tz_aware
from market_data.budget import RequestAccountingEntry
from market_data.fulfillment import CapabilityFulfillmentResult
from market_data.providers import ProviderMetadata
from market_data.resolution import ResolutionMethod, ResolutionResult

SNAPSHOT_SCHEMA_VERSION = "v1"
SNAPSHOT_IDENTITY_NAMESPACE = "asa.market_snapshot/v1"


@dataclass(frozen=True, slots=True)
class SnapshotRequest:
    as_of: datetime
    requested_capabilities: tuple[MarketCapability, ...]
    required_capabilities: tuple[MarketCapability, ...]
    schema_version: str = SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_tz_aware(self.as_of, "SnapshotRequest", "as_of")
        requested = tuple(sorted(set(self.requested_capabilities), key=lambda item: item.value))
        required = tuple(sorted(set(self.required_capabilities), key=lambda item: item.value))
        if not requested or not set(required).issubset(requested):
            raise DomainInvariantError("SnapshotRequest capability sets are inconsistent")
        if self.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise DomainInvariantError("SnapshotRequest schema version is unsupported")
        object.__setattr__(self, "requested_capabilities", requested)
        object.__setattr__(self, "required_capabilities", required)


@dataclass(frozen=True, slots=True)
class SnapshotValidationMetadata:
    report_id: str
    provider_id: str
    disposition: str

    def __post_init__(self) -> None:
        for name in ("report_id", "provider_id", "disposition"):
            value = getattr(self, name)
            if not value or value != value.strip():
                raise DomainInvariantError(f"SnapshotValidationMetadata {name} must be normalized")


@dataclass(frozen=True, slots=True)
class SnapshotCompleteness:
    requested_capabilities: tuple[MarketCapability, ...]
    resolved_capabilities: tuple[MarketCapability, ...]
    unresolved_capabilities: tuple[MarketCapability, ...]
    missing_required_capabilities: tuple[MarketCapability, ...]

    def __post_init__(self) -> None:
        requested = set(self.requested_capabilities)
        if set(self.resolved_capabilities) | set(self.unresolved_capabilities) != requested:
            raise DomainInvariantError("SnapshotCompleteness does not cover every request")
        if set(self.resolved_capabilities) & set(self.unresolved_capabilities):
            raise DomainInvariantError("SnapshotCompleteness resolution sets overlap")
        if not set(self.missing_required_capabilities).issubset(self.unresolved_capabilities):
            raise DomainInvariantError("SnapshotCompleteness required failures are inconsistent")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    snapshot_id: str
    snapshot_digest: str
    schema_version: str
    as_of: datetime
    requested_capabilities: tuple[MarketCapability, ...]
    observations: tuple[MarketObservation, ...]
    resolution_results: tuple[ResolutionResult, ...]
    provider_metadata: tuple[ProviderMetadata, ...]
    validation_metadata: tuple[SnapshotValidationMetadata, ...]
    request_accounting: tuple[RequestAccountingEntry, ...]
    completeness: SnapshotCompleteness
    evidence: tuple[EvidenceReference, ...]

    def __post_init__(self) -> None:
        require_tz_aware(self.as_of, "MarketSnapshot", "as_of")
        if self.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise DomainInvariantError("MarketSnapshot schema version is unsupported")
        if any(item.recorded_time > self.as_of for item in self.observations):
            raise DomainInvariantError("MarketSnapshot as_of precedes included recording")
        expected = market_snapshot_digest(self)
        if (
            self.snapshot_digest != expected
            or self.snapshot_id != f"{SNAPSHOT_IDENTITY_NAMESPACE}:{expected}"
        ):
            raise DomainInvariantError("MarketSnapshot identity is not content-derived")


class MarketSnapshotBuilder:
    def build(
        self,
        request: SnapshotRequest,
        fulfillments: tuple[CapabilityFulfillmentResult, ...],
        resolutions: tuple[ResolutionResult, ...],
        provider_metadata: tuple[ProviderMetadata, ...],
        validation_metadata: tuple[SnapshotValidationMetadata, ...],
        request_accounting: tuple[RequestAccountingEntry, ...],
    ) -> MarketSnapshot:
        fulfillment_by_capability = {item.request.capability: item for item in fulfillments}
        resolution_by_capability = {item.capability: item for item in resolutions}
        requested = set(request.requested_capabilities)
        if (
            len(fulfillment_by_capability) != len(fulfillments)
            or set(fulfillment_by_capability) != requested
        ):
            raise DomainInvariantError("Snapshot requires one fulfillment per capability")
        if len(resolution_by_capability) != len(resolutions) or not set(
            resolution_by_capability
        ).issubset(requested):
            raise DomainInvariantError("Snapshot resolutions must be unique requested capabilities")

        observations = tuple(
            sorted(
                {
                    observation.observation_id: observation
                    for fulfillment in fulfillments
                    for attempt in fulfillment.attempts
                    for observation in attempt.observations
                }.values(),
                key=lambda item: (
                    item.capability.value,
                    item.subject.subject_identity,
                    item.effective_time,
                    item.provenance.provider_id,
                    item.observation_id,
                ),
            )
        )
        included_providers = {item.provenance.provider_id for item in observations}
        metadata = tuple(
            sorted(
                (
                    item
                    for item in provider_metadata
                    if item.identity.provider_id in included_providers
                ),
                key=lambda item: item.identity.provider_id,
            )
        )
        if {item.identity.provider_id for item in metadata} != included_providers:
            raise DomainInvariantError("Snapshot lacks bounded metadata for an included provider")
        ordered_resolutions = tuple(sorted(resolutions, key=lambda item: item.capability.value))
        resolved = tuple(
            item.capability
            for item in ordered_resolutions
            if item.method is not ResolutionMethod.UNRESOLVED
        )
        resolved_set = set(resolved)
        unresolved = tuple(
            item for item in request.requested_capabilities if item not in resolved_set
        )
        missing_required = tuple(
            item for item in unresolved if item in request.required_capabilities
        )
        completeness = SnapshotCompleteness(
            request.requested_capabilities, resolved, unresolved, missing_required
        )
        evidence = tuple(
            sorted(
                {
                    (item.kind.value, item.referenced_id): item
                    for observation in observations
                    for item in observation.provenance.evidence
                }.values(),
                key=lambda item: (item.kind.value, item.referenced_id),
            )
        )
        ordered_validation = tuple(
            sorted(validation_metadata, key=lambda item: (item.provider_id, item.report_id))
        )
        ordered_accounting = tuple(
            sorted(request_accounting, key=lambda item: item.authorization_id)
        )
        values: dict[str, object] = {
            "schema_version": request.schema_version,
            "as_of": request.as_of,
            "requested_capabilities": request.requested_capabilities,
            "observations": observations,
            "resolution_results": ordered_resolutions,
            "provider_metadata": metadata,
            "validation_metadata": ordered_validation,
            "request_accounting": ordered_accounting,
            "completeness": completeness,
            "evidence": evidence,
        }
        digest = _digest(values)
        return MarketSnapshot(
            f"{SNAPSHOT_IDENTITY_NAMESPACE}:{digest}",
            digest,
            request.schema_version,
            request.as_of,
            request.requested_capabilities,
            observations,
            ordered_resolutions,
            metadata,
            ordered_validation,
            ordered_accounting,
            completeness,
            evidence,
        )


def market_snapshot_digest(snapshot: MarketSnapshot) -> str:
    return _digest(
        {
            "schema_version": snapshot.schema_version,
            "as_of": snapshot.as_of,
            "requested_capabilities": snapshot.requested_capabilities,
            "observations": snapshot.observations,
            "resolution_results": snapshot.resolution_results,
            "provider_metadata": snapshot.provider_metadata,
            "validation_metadata": snapshot.validation_metadata,
            "request_accounting": snapshot.request_accounting,
            "completeness": snapshot.completeness,
            "evidence": snapshot.evidence,
        }
    )


def market_snapshot_to_data(snapshot: MarketSnapshot) -> dict[str, object]:
    return cast(dict[str, object], _canonical(snapshot))


def serialize_market_snapshot(snapshot: MarketSnapshot) -> str:
    return json.dumps(_canonical(snapshot), sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _canonical(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return {"$decimal": format(value, "f")}
    if isinstance(value, dict):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported snapshot value type: {type(value).__name__}")
