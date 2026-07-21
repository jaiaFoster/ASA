"""Immutable normalized data-value contract and primitive invariants.

ASA-CORE-001A, hardened by ASA-CORE-002. These are structural identity
constraints on what the domain model may hold — not reconciliation,
strategy, or calculation behavior.

A **normalized value** is the only shape a domain ``value`` field may take:

- a scalar: ``None``, ``bool``, ``int``, a **finite** ``float``, a **finite**
  ``Decimal``, ``str``, or a timezone-aware ``datetime``
- an **immutable mapping**: a non-empty ``tuple`` whose every element is a
  ``(str, normalized value)`` pair with **unique** keys, or
- a ``tuple`` of normalized values (an ordered sequence).

Any non-empty tuple whose elements are all ``(str, value)`` pairs IS an
immutable mapping — there is no separate mapping type. Non-finite numbers
(NaN, +/-Infinity, in either ``float`` or ``Decimal`` form) and duplicate
mapping keys are rejected recursively. Mutable containers (``list``,
``dict``, ``set``, ``bytearray``) are never normalized values, so no domain
entity can contain a mutable nested value.

Deterministic key ordering of mappings is a canonicalization concern owned
by the Observation Layer (``observation/canonicalization.py``); the domain
contract accepts any key order but guarantees uniqueness.
"""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal


class DomainInvariantError(ValueError):
    """A domain object was constructed in violation of a structural invariant."""


def _is_finite_scalar(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Decimal):
        return value.is_finite()
    return isinstance(value, (int, str))


def is_mapping_pairs(value: object) -> bool:
    """True if ``value`` is shaped as an immutable mapping (see module doc)."""
    return (
        isinstance(value, tuple)
        and len(value) > 0
        and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        )
    )


def is_normalized_value(value: object) -> bool:
    """True if ``value`` satisfies the immutable normalized-value contract."""
    if value is None or _is_finite_scalar(value):
        return True
    if isinstance(value, (float, Decimal)):
        return False  # non-finite float/Decimal
    if isinstance(value, datetime):
        return value.tzinfo is not None
    if isinstance(value, tuple):
        if is_mapping_pairs(value):
            keys = [k for k, _ in value]
            if len(keys) != len(set(keys)):
                return False  # duplicate mapping keys
            return all(is_normalized_value(v) for _, v in value)
        return all(is_normalized_value(item) for item in value)
    return False


def require_normalized(value: object, owner: str, field_name: str) -> None:
    if not is_normalized_value(value):
        raise DomainInvariantError(
            f"{owner}.{field_name} is not an immutable normalized value "
            f"({type(value).__name__!s}). Allowed: finite scalars, tz-aware "
            f"datetimes, unique-keyed mapping tuples, and (nested) tuples — "
            f"never list/dict/set, NaN, or Infinity."
        )


def require_tz_aware(value: datetime, owner: str, field_name: str) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise DomainInvariantError(
            f"{owner}.{field_name} must be timezone-aware; got naive {value!r}"
        )


def require_unit_interval(value: float | Decimal, owner: str, field_name: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise DomainInvariantError(f"{owner}.{field_name} must be finite; got {value!r}")
    if isinstance(value, Decimal) and not value.is_finite():
        raise DomainInvariantError(f"{owner}.{field_name} must be finite; got {value!r}")
    if not (0 <= value <= 1):
        raise DomainInvariantError(
            f"{owner}.{field_name} must be within [0, 1]; got {value!r}"
        )


def require_positive(value: int, owner: str, field_name: str) -> None:
    """Require an exact positive integer — bool and non-int are rejected."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainInvariantError(
            f"{owner}.{field_name} must be an exact integer "
            f"(bool is not accepted); got {type(value).__name__} {value!r}"
        )
    if value < 1:
        raise DomainInvariantError(
            f"{owner}.{field_name} must be a positive integer; got {value!r}"
        )


def require_finite_decimal(value: object, owner: str, field_name: str) -> None:
    """Financial metrics must be finite Decimal values — never float/int/bool."""
    if not isinstance(value, Decimal):
        raise DomainInvariantError(
            f"{owner}.{field_name} must be a Decimal; got {type(value).__name__} {value!r}"
        )
    if not value.is_finite():
        raise DomainInvariantError(
            f"{owner}.{field_name} must be finite; got {value!r}"
        )
