"""Observation repository errors (ASA-CORE-002)."""
from __future__ import annotations


class ObservationRepositoryError(Exception):
    """Base error for Observation repository operations."""


class DuplicateObservationError(ObservationRepositoryError):
    """The exact same Observation record was appended twice."""

    def __init__(self, observation_id: str) -> None:
        super().__init__(f"duplicate observation append rejected: {observation_id}")
        self.observation_id = observation_id


class IdentityCollisionError(ObservationRepositoryError):
    """A different record was appended under an already-stored identity.

    The original record is preserved; the colliding record is rejected.
    """

    def __init__(self, observation_id: str) -> None:
        super().__init__(
            f"identity collision rejected: a different record is already "
            f"stored under {observation_id}; original preserved"
        )
        self.observation_id = observation_id


class ObservationNotFoundError(ObservationRepositoryError):
    """No Observation is stored under the requested identity."""

    def __init__(self, observation_id: str) -> None:
        super().__init__(f"observation not found: {observation_id}")
        self.observation_id = observation_id
