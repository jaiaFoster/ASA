"""Immutable normalized data-value contract and primitive invariants.

ASA-CORE-001A. These are structural identity constraints on what the domain
model may hold — not reconciliation, strategy, or calculation behavior.

A **normalized value** is the only shape a domain ``value`` field may take:

- a scalar: ``None``, ``bool``, ``int``, ``float``, ``Decimal``, ``str``,
  or a timezone-aware ``datetime``
- a ``tuple`` of normalized values (an ordered sequence), or
- a ``tuple`` of ``(str, normalized value)`` pairs (a mapping rendered
  immutably; keys are field names from the Observation schema).

Mutable containers (``list``, ``dict``, ``set``, ``bytearray``) are never
normalized values, so no domain entity can contain a mutable nested value.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

_SCALAR_TYPES = (bool, int, float, Decimal, str)


class DomainInvariantError(ValueError):
    """A domain object was constructed in violation of a structural invariant."""


def is_normalized_value(value: object) -> bool:
    """True if ``value`` satisfies the immutable normalized-value contract."""
    if value is None or isinstance(value, _SCALAR_TYPES):
        return True
    if isinstance(value, datetime):
        return value.tzinfo is not None
    if isinstance(value, tuple):
        return all(
            (
                isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[0], str)
                and is_normalized_value(item[1])
            )
            or is_normalized_value(item)
            for item in value
        )
    return False


def require_normalized(value: object, owner: str, field_name: str) -> None:
    if not is_normalized_value(value):
        raise DomainInvariantError(
            f"{owner}.{field_name} is not an immutable normalized value: "
            f"{type(value).__name__!s}. Allowed: scalars, tz-aware datetimes, "
            f"and (nested) tuples — never list/dict/set."
        )


def require_tz_aware(value: datetime, owner: str, field_name: str) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise DomainInvariantError(
            f"{owner}.{field_name} must be timezone-aware; got naive {value!r}"
        )


def require_unit_interval(value: float | Decimal, owner: str, field_name: str) -> None:
    if not (0 <= value <= 1):
        raise DomainInvariantError(
            f"{owner}.{field_name} must be within [0, 1]; got {value!r}"
        )


def require_positive(value: int, owner: str, field_name: str) -> None:
    if value < 1:
        raise DomainInvariantError(
            f"{owner}.{field_name} must be a positive integer; got {value!r}"
        )
