"""Canonical Fact repository errors (ASA-CORE-003)."""
from __future__ import annotations


class FactRepositoryError(Exception):
    """Base error for Canonical Fact repository operations."""


class DuplicateFactError(FactRepositoryError):
    """The exact same Canonical Fact record was appended twice."""

    def __init__(self, fact_id: str, version: int) -> None:
        super().__init__(
            f"duplicate canonical fact append rejected: {fact_id} v{version}"
        )
        self.fact_id = fact_id
        self.version = version


class FactIdentityCollisionError(FactRepositoryError):
    """A different record was appended under an already-stored fact_id.

    The original record is preserved; the colliding record is rejected.
    """

    def __init__(self, fact_id: str) -> None:
        super().__init__(
            f"canonical fact identity collision rejected: a different "
            f"record is already stored under {fact_id}; original preserved"
        )
        self.fact_id = fact_id


class NonMonotonicVersionError(FactRepositoryError):
    """An appended fact's version does not extend its group's history by exactly one.

    Enforces monotonic versioning as a repository-level invariant, in
    addition to ``reconciliation.engine.reconcile``'s own version
    computation — defense in depth against a caller appending out of
    sequence or from stale state.
    """

    def __init__(self, fact_type: str, effective_time: object,
                expected_version: int, got_version: int) -> None:
        super().__init__(
            f"non-monotonic version for ({fact_type!r}, {effective_time!r}): "
            f"expected version {expected_version}, got {got_version}"
        )
        self.fact_type = fact_type
        self.effective_time = effective_time
        self.expected_version = expected_version
        self.got_version = got_version


class FactNotFoundError(FactRepositoryError):
    """No Canonical Fact is stored for the requested group."""

    def __init__(self, fact_type: str, effective_time: object) -> None:
        super().__init__(f"no canonical fact found for ({fact_type!r}, {effective_time!r})")
        self.fact_type = fact_type
        self.effective_time = effective_time
