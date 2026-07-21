"""Deterministic, versioned Observation identity (ASA-CORE-002).

Identity algorithm ``asa.observation`` **v1**:

    sha256(
        "asa.observation" NL "v1" NL
        serialize(provider_id) NL
        serialize(observation_type) NL
        serialize(effective_time) NL
        serialize(canonicalize(value))
    ) -> lowercase hexadecimal string

No UUIDs, no repository sequence numbers, no insertion time, no randomness.
The same logical Observation input always produces the same identity;
mapping key order, timezone representation, and Decimal exponent form do
not affect it (see ``observation/canonicalization.py``). Any change to the
serialization contract requires a new algorithm version, never a silent
change to v1.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from domain.values import DomainInvariantError, require_tz_aware
from domain.canonicalization import _serialize, serialize_canonical

IDENTITY_NAMESPACE = "asa.observation"
IDENTITY_VERSION = "v1"


def observation_identity(
    provider_id: str,
    observation_type: str,
    effective_time: datetime,
    value: object,
) -> str:
    """Derive the deterministic v1 identity for an Observation's content."""
    if not provider_id:
        raise DomainInvariantError("observation_identity: provider_id must be non-empty")
    if not observation_type:
        raise DomainInvariantError("observation_identity: observation_type must be non-empty")
    require_tz_aware(effective_time, "observation_identity", "effective_time")

    payload = "\n".join(
        (
            IDENTITY_NAMESPACE,
            IDENTITY_VERSION,
            _serialize(provider_id),
            _serialize(observation_type),
            _serialize(effective_time),
            serialize_canonical(value),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
