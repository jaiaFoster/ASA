"""Observation Layer (ADR-001).

Owns Observation storage and identity.
May depend on: observation, providers, domain (ADR-004).

Public contract (ASA-CORE-002): the repository, its errors, and the
versioned identity function. Canonicalization internals stay in
``observation.canonicalization`` and are not exported here.
"""
from observation.errors import (
    DuplicateObservationError,
    IdentityCollisionError,
    ObservationNotFoundError,
    ObservationRepositoryError,
)
from observation.identity import (
    IDENTITY_NAMESPACE,
    IDENTITY_VERSION,
    observation_identity,
)
from observation.repository import InMemoryObservationRepository

__all__ = [
    "DuplicateObservationError",
    "IDENTITY_NAMESPACE",
    "IDENTITY_VERSION",
    "IdentityCollisionError",
    "InMemoryObservationRepository",
    "ObservationNotFoundError",
    "ObservationRepositoryError",
    "observation_identity",
]
