"""Canonical form and deterministic serialization of normalized values.

Originally introduced in ASA-CORE-002 as ``observation/canonicalization.py``
(internal to the Observation Layer); relocated here in ASA-CORE-004 because
the Indicator Layer also needs it for indicator identity, and cannot depend
on ``observation/`` (ADR-004, narrowed for ``indicators/`` — see
``tests/architecture/test_indicator_boundaries.py``). Canonicalization is a
cross-cutting concern over the normalized-value contract already owned by
``domain/values.py`` (Constitution Law 3: one calculation, one home), not
specifically an Observation-layer concern — this move corrects the original
placement rather than working around it.

``observation/canonicalization.py`` re-exports these names for backward
compatibility; new code in any layer should import from here directly.

Canonical form:
- immutable mappings (tuple-of-``(str, value)``-pairs) are sorted by key,
  recursively — key order never carries meaning;
- sequences keep their order — order is meaning;
- scalars are unchanged.

Serialization contract (versioned via each consuming layer's own identity
algorithm — e.g. ``asa.observation`` v1, ``asa.canonical_fact`` v1,
``asa.indicator`` v1):
- every value carries an explicit type tag, so ``True`` and ``1`` differ,
  and a mapping differs from the sequence of its pairs;
- strings are length-prefixed, so no escaping ambiguity exists;
- datetimes are normalized to UTC and rendered in ISO-8601 form, so
  timezone-equivalent datetimes serialize identically;
- Decimals are rendered from their exact decimal representation, normalized
  to remove exponent/trailing-zero variance — never through float.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from domain.values import DomainInvariantError, is_mapping_pairs, is_normalized_value


def canonicalize_value(value: object) -> object:
    """Return the canonical form of a normalized value.

    Mapping keys are sorted recursively; sequence order is preserved.
    Raises DomainInvariantError if ``value`` is not a normalized value.
    """
    if not is_normalized_value(value):
        raise DomainInvariantError(f"not a normalized value: {value!r}")
    return _canonicalize(value)


def _canonicalize(value: object) -> object:
    if isinstance(value, tuple):
        if is_mapping_pairs(value):
            return tuple(
                (key, _canonicalize(item))
                for key, item in sorted(value, key=lambda pair: pair[0])
            )
        return tuple(_canonicalize(item) for item in value)
    return value


def serialize_canonical(value: object) -> str:
    """Deterministically serialize a normalized value (canonicalizing first)."""
    return _serialize(canonicalize_value(value))


def _canonical_decimal(value: Decimal) -> str:
    """Exact canonical decimal text: no exponent, no trailing zeros, no
    context-precision rounding (``Decimal.normalize()`` would round at the
    context's significant-digit limit and is deliberately not used)."""
    text = format(value, "f")  # exact fixed-point rendering
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _serialize_str(text: str) -> str:
    return f"s:{len(text.encode('utf-8'))}:{text}"


def _serialize(value: object) -> str:
    if value is None:
        return "z:"
    if isinstance(value, bool):  # before int — bool is not an integer here
        return f"b:{'true' if value else 'false'}"
    if isinstance(value, int):
        return f"i:{value}"
    if isinstance(value, float):
        return f"f:{value!r}"
    if isinstance(value, Decimal):
        return f"d:{_canonical_decimal(value)}"
    if isinstance(value, str):
        return _serialize_str(value)
    if isinstance(value, datetime):
        return f"t:{value.astimezone(timezone.utc).isoformat()}"
    if isinstance(value, tuple):
        if is_mapping_pairs(value):
            inner = ",".join(
                f"{_serialize_str(key)}={_serialize(item)}" for key, item in value
            )
            return f"m:{{{inner}}}"
        inner = ",".join(_serialize(item) for item in value)
        return f"l:[{inner}]"
    raise DomainInvariantError(f"unserializable value type: {type(value).__name__}")
