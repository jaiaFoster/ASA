"""Rich Universal Result values (SPRINT-009R/EPIC-R2).

TypedValue is the one thing every strategy's own metrics/economics
namespace entry is, regardless of what that strategy computes -- the same
generalize_before_specialize principle EPIC-6's own UniversalScreeningResult
already applies to the envelope shape, applied here to the value inside it.
A strategy that used to have to render a Decimal, bool, or datetime down to
a bare str (losing type information at the boundary) now wraps it in a
TypedValue instead, and the exact original value comes back out unchanged
through ``native()`` -- "universal results preserve complete strategy
outputs" is enforced by round-tripping through this module, not merely
documented.

Deliberately closed to seven kinds, matching EPIC-R2's own
supported_types list exactly: decimal, integer, boolean, string, datetime,
duration, and structured (a JSON-shaped mapping or sequence of any mix of
the other six, nested arbitrarily deep, for a strategy whose native output
is not a single scalar).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Union

from domain.values import DomainInvariantError, require_tz_aware

JsonScalar = str | int | float | bool | None
# X | Y syntax cannot hold a forward-reference string operand at runtime (this is a value
# assignment, not an annotation -- `from __future__ import annotations` does not defer it).
JsonValue = Union[JsonScalar, "list[JsonValue]", "dict[str, JsonValue]"]  # noqa: UP007


class ValueType(str, Enum):
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"
    DATETIME = "datetime"
    DURATION = "duration"
    STRUCTURED = "structured"


@dataclass(frozen=True, slots=True)
class TypedValue:
    """``encoded`` is always this value's own canonical string form -- for
    every kind but STRUCTURED, decoding it is a single stdlib constructor
    call; STRUCTURED's ``encoded`` is a sort_keys=True JSON document, so two
    TypedValues built from an equal structured value are always
    byte-identical, matching this codebase's established canonicalization
    convention (domain/canonicalization.py's own json.dumps(...,
    sort_keys=True, separators=(",", ":")) idiom) rather than inventing a
    second one here.
    """

    value_type: ValueType
    encoded: str

    def __post_init__(self) -> None:
        if not isinstance(self.value_type, ValueType):
            raise DomainInvariantError("TypedValue.value_type must be a ValueType")
        if self.encoded == "" and self.value_type is not ValueType.STRING:
            raise DomainInvariantError(
                f"TypedValue.encoded must be non-empty for {self.value_type.value}"
            )
        # Round-trip now, at construction time, rather than deferring the failure to
        # whatever caller eventually calls native() -- an invalid TypedValue must never
        # be constructible in the first place.
        self.native()

    @classmethod
    def of_decimal(cls, value: Decimal) -> TypedValue:
        return cls(ValueType.DECIMAL, str(value))

    @classmethod
    def of_integer(cls, value: int) -> TypedValue:
        return cls(ValueType.INTEGER, str(value))

    @classmethod
    def of_boolean(cls, value: bool) -> TypedValue:
        return cls(ValueType.BOOLEAN, "true" if value else "false")

    @classmethod
    def of_string(cls, value: str) -> TypedValue:
        return cls(ValueType.STRING, value)

    @classmethod
    def of_datetime(cls, value: datetime) -> TypedValue:
        require_tz_aware(value, "TypedValue", "of_datetime")
        return cls(ValueType.DATETIME, value.isoformat())

    @classmethod
    def of_duration(cls, value: timedelta) -> TypedValue:
        return cls(ValueType.DURATION, str(value.total_seconds()))

    @classmethod
    def of_structured(cls, value: Mapping[str, JsonValue] | Sequence[JsonValue]) -> TypedValue:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return cls(ValueType.STRUCTURED, encoded)

    def native(self) -> object:
        """Decode back to the exact kind of Python value the ``of_*``
        constructor was given -- the one place every reader of a TypedValue
        should go through, so a decoding rule is written once, not
        re-implemented at every call site.
        """
        try:
            if self.value_type is ValueType.DECIMAL:
                return Decimal(self.encoded)
            if self.value_type is ValueType.INTEGER:
                return int(self.encoded)
            if self.value_type is ValueType.BOOLEAN:
                if self.encoded not in ("true", "false"):
                    raise DomainInvariantError("TypedValue boolean encoding must be true/false")
                return self.encoded == "true"
            if self.value_type is ValueType.STRING:
                return self.encoded
            if self.value_type is ValueType.DATETIME:
                value = datetime.fromisoformat(self.encoded)
                require_tz_aware(value, "TypedValue", "native")
                return value
            if self.value_type is ValueType.DURATION:
                return timedelta(seconds=float(self.encoded))
            return json.loads(self.encoded)
        except (InvalidOperation, ValueError) as exc:
            raise DomainInvariantError(
                f"TypedValue.encoded is not a valid {self.value_type.value}"
            ) from exc

    def to_json(self) -> dict[str, str]:
        """The one JSON-shaped encoding this module hands to a storage
        boundary (strategy_runtime.persistence's own concrete Postgres
        implementation lives in asa/, not here) -- plain str/str so it
        survives an ordinary json.dumps() with no custom encoder.
        """
        return {"type": self.value_type.value, "value": self.encoded}

    @classmethod
    def from_json(cls, data: Mapping[str, str]) -> TypedValue:
        try:
            value_type = ValueType(data["type"])
        except ValueError as exc:
            raise DomainInvariantError(f"Unknown TypedValue type {data.get('type')!r}") from exc
        return cls(value_type, data["value"])
