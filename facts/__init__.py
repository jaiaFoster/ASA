"""Canonical Fact Layer (ADR-001).

Owns Canonical Fact storage and versioning orchestration; deterministic
reconciliation logic itself lives in ``reconciliation/`` (ASA-CORE-003).
May depend on: facts, reconciliation, observation, providers, domain (ADR-004).
"""
from facts.errors import (
    DuplicateFactError,
    FactIdentityCollisionError,
    FactNotFoundError,
    FactRepositoryError,
    NonMonotonicVersionError,
)
from facts.repository import InMemoryCanonicalFactRepository

__all__ = [
    "DuplicateFactError",
    "FactIdentityCollisionError",
    "FactNotFoundError",
    "FactRepositoryError",
    "InMemoryCanonicalFactRepository",
    "NonMonotonicVersionError",
]
