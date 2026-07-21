# Strategy Type System v1

**Type-system version:** `1.0.0`

The Strategy Type System implements ASA-ARCH-003's closed, deterministic graph-connection
vocabulary. It owns exact type resolution, parameterized type shape, value validation, and
compatibility. It performs no conversion, parsing from provider identifiers, component execution,
or graph traversal.

## Closed catalog

V1 defines:

- primitives: Boolean, Integer, Decimal, Text, Date, Instant;
- financial values: Currency, Money, Ratio, Probability, Quantity;
- domain values: Instrument, CanonicalFact, IndicatorValue, Evidence,
  ExpectedOutcomeMetrics, Opportunity;
- bounded Enum;
- immutable Optional, List, and Map containers.

Every type reference pins an exact name and Semantic Version. Optional and List take one type
argument; Map takes key and value arguments. Other types take no arguments. Unknown types,
versions, argument counts, and qualifiers fail closed.

Money requires an uppercase three-letter currency qualifier. Money values with different currency
qualifiers are not compatible. Enum requires a non-empty unique tuple of allowed string values.
Other v1 types reject qualifiers.

## Compatibility

V1 compatibility is nominal exact equality over the complete type reference, including version,
arguments, and qualifiers. There is no implicit numeric narrowing or widening, optional
unwrapping, text parsing, symbol resolution, unit conversion, or currency conversion. Integer to
Decimal requires a future explicit registered conversion Component; the type system does not do
it implicitly.

## Typed values

`TypedValue` associates one exact type reference with one immutable value. `ComponentValues` is a
sorted, unique-name tuple of Typed Values used for Component inputs, effective parameters, and
outputs. Mutable list, dictionary, set, bytearray, or nested mutable container payloads are
rejected before type validation.

Validation is strict:

- Boolean is not Integer;
- financial numerics are finite Decimal values;
- Probability is within `[0, 1]`;
- Date excludes datetime;
- Instant is timezone-aware;
- Currency is uppercase and three letters;
- domain values must be instances of the canonical existing domain contract;
- List uses tuples and validates every item;
- Map uses immutable pair tuples and validates every key and value;
- Optional permits null or one value valid for its argument;
- Enum permits only a declared value.

The immutable catalog has a deterministic identity independent of definition input order. Type
compatibility rules are architecture-owned; adding or changing one requires a reviewed
architecture revision rather than a registry tweak.
