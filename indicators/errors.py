"""Indicator engine, registry, and repository errors (ASA-CORE-004)."""
from __future__ import annotations


class IndicatorError(Exception):
    """Base error for all indicator operations."""


# ---------------------------------------------------------------------------
# Calculation errors
# ---------------------------------------------------------------------------

class InsufficientDataError(IndicatorError):
    """Not enough Canonical Facts were supplied for the requested calculation."""

    def __init__(self, indicator_type: str, required: int, got: int) -> None:
        super().__init__(
            f"{indicator_type} requires at least {required} fact(s); got {got}"
        )
        self.indicator_type = indicator_type
        self.required = required
        self.got = got


class InconsistentFactGroupError(IndicatorError):
    """Facts supplied to one calculation do not share a fact_type."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class IndicatorCalculationError(IndicatorError):
    """A calculation could not produce a well-defined result (e.g. division by zero)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Registry errors
# ---------------------------------------------------------------------------

class DuplicateIndicatorRegistrationError(IndicatorError):
    """An indicator_type was registered more than once."""

    def __init__(self, indicator_type: str) -> None:
        super().__init__(f"indicator_type already registered: {indicator_type!r}")
        self.indicator_type = indicator_type


class UnknownIndicatorTypeError(IndicatorError):
    """No calculation is registered for the requested indicator_type."""

    def __init__(self, indicator_type: str) -> None:
        super().__init__(f"no indicator registered for type: {indicator_type!r}")
        self.indicator_type = indicator_type


# ---------------------------------------------------------------------------
# Repository errors
# ---------------------------------------------------------------------------

class IndicatorRepositoryError(IndicatorError):
    """Base error for Indicator repository operations."""


class DuplicateIndicatorError(IndicatorRepositoryError):
    """The exact same Indicator record was appended twice."""

    def __init__(self, indicator_id: str, version: int) -> None:
        super().__init__(
            f"duplicate indicator append rejected: {indicator_id} v{version}"
        )
        self.indicator_id = indicator_id
        self.version = version


class IndicatorIdentityCollisionError(IndicatorRepositoryError):
    """A different record was appended under an already-stored indicator_id.

    The original record is preserved; the colliding record is rejected.
    """

    def __init__(self, indicator_id: str) -> None:
        super().__init__(
            f"indicator identity collision rejected: a different record is "
            f"already stored under {indicator_id}; original preserved"
        )
        self.indicator_id = indicator_id


class NonMonotonicIndicatorVersionError(IndicatorRepositoryError):
    """An appended indicator's version does not extend its group's history by exactly one."""

    def __init__(self, indicator_type: str, effective_time: object,
                expected_version: int, got_version: int) -> None:
        super().__init__(
            f"non-monotonic version for ({indicator_type!r}, {effective_time!r}): "
            f"expected version {expected_version}, got {got_version}"
        )
        self.indicator_type = indicator_type
        self.effective_time = effective_time
        self.expected_version = expected_version
        self.got_version = got_version


class IndicatorNotFoundError(IndicatorRepositoryError):
    """No Indicator is stored for the requested group."""

    def __init__(self, indicator_type: str, effective_time: object) -> None:
        super().__init__(
            f"no indicator found for ({indicator_type!r}, {effective_time!r})"
        )
        self.indicator_type = indicator_type
        self.effective_time = effective_time
