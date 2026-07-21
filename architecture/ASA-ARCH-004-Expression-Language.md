# ASA-ARCH-004: Expression Language Specification

**Status:** Proposed — Founder merge required

**Date:** 2026-07-21

**Patch:** STRAT-007A

**Language version:** `1.0.0`

## Context

ASA-ARCH-003 requires a closed, deterministic expression language for conditions, scoring,
filtering, and parameter evaluation inside Strategy Components. It freezes the safety boundary but
does not choose the concrete grammar, Decimal context, type and null semantics, function
signatures, resource limits, canonical AST, or compiled identity. Issue #81 records why those
choices cannot be invented inside STRAT-007: they affect public manifests, replay, explainability,
and future tooling.

This document is the normative v1 contract for parsing, compilation, validation, evaluation,
serialization, identity, errors, replay, and trace output. Implementations may optimize internally
only when observable results, errors, identities, and traces remain identical.

## Boundary

An ASA expression is one side-effect-free expression. It contains no statement, assignment,
declaration, user-defined function, lambda, loop, comprehension, recursion, import, attribute
access, index mutation, object construction, reflection, exception handling, I/O, filesystem,
network, clock, randomness, provider access, persistence, or broker behavior.

Expressions cannot create variables. Bare identifiers reference an immutable input environment
provided by the caller. The environment is complete before evaluation and cannot change during
evaluation. An unknown identifier is a compile-time error.

The language cannot construct List or Map values in v1. Finite immutable collections may enter
only as typed input values. This is the v1 meaning of “allocation prohibited”: parsing and Core's
bounded immutable AST construction are permitted implementation necessities; evaluated language
code cannot allocate arbitrary collections or objects.

## Lexical Grammar

Source is Unicode text limited to 16,384 UTF-8 bytes. Tokens are separated by ASCII whitespace.
Whitespace is never semantic. Comments are forbidden.

Identifiers match `[A-Za-z][A-Za-z0-9_]*`. Keywords and built-in function names are reserved and
cannot be input identifiers.

### Literals

- Integer: decimal digits with no leading zero except `0`, range
  `[-9223372036854775808, 9223372036854775807]`. The sign is a unary operator; the minimum value is
  accepted as the folded form of unary minus applied to `9223372036854775808`.
- Decimal: digits, a decimal point, and digits on both sides, optionally followed by `e` or `E`, an
  optional sign, and exponent digits. Examples: `0.5`, `12.00`, `1.25e-3`. It compiles directly
  from source text to Decimal128. IEEE binary float never exists.
- Boolean: `true` and `false`.
- String: double-quoted JSON string syntax. Its decoded Unicode scalar sequence is immutable.
- Date: `date("YYYY-MM-DD")`, using the ISO-8601 proleptic Gregorian calendar.
- Duration: `duration(days: I, hours: I, minutes: I, seconds: I)`, where arguments are named,
  optional, unique Integer literals; at least one is required. Names appear in that canonical
  order. Units are fixed elapsed time; months and years are forbidden.
- Null: `null`, the singleton Unknown value.

Date and Duration are grammar-recognized literal forms, not ordinary user-callable constructors.
Dates carry no local timezone. Date-time/Instant literals are not part of v1. Date arithmetic uses
UTC calendar semantics and therefore has no daylight-saving behavior. Leap years follow ISO-8601;
leap seconds are ignored.

### Punctuation

`(`, `)`, `,`, and `:` are the only punctuation outside operators and literal text. Parentheses
group expressions. There is no member access, subscript syntax, list/map literal, semicolon, or
statement separator.

## Syntactic Grammar

The normative grammar is EBNF:

```text
expression       = logical_or ;
logical_or       = logical_and, { "or", logical_and } ;
logical_and      = comparison, { "and", comparison } ;
comparison       = additive, [ comparison_op, additive ] ;
comparison_op    = "==" | "!=" | "<" | "<=" | ">" | ">=" ;
additive         = multiplicative, { ("+" | "-"), multiplicative } ;
multiplicative   = unary, { ("*" | "/" | "%"), unary } ;
unary            = [ "+" | "-" | "not" ], unary | primary ;
primary          = literal | identifier | function_call | "(", expression, ")" ;
function_call    = function_name, "(", [ expression, { ",", expression } ], ")" ;
```

Binary arithmetic and logical operators associate left-to-right. Unary operators are prefix and
associate right-to-left. Comparison chaining (`a < b < c`) is forbidden; use explicit Boolean
operations. Logical operators have the lowest precedence, comparisons next, then additive,
multiplicative, and unary highest.

The parser must implement this grammar directly or prove byte-for-byte equivalent accepted and
rejected inputs. Host-language AST nodes are never the canonical AST.

## Type Semantics

Compilation receives the exact `StrategyTypeReference` of every input identifier. It produces one
exact result type or a compile-time type error. V1 uses the Strategy Type System from STRAT-006.

- Unary `+` and `-`: Integer → Integer; Decimal → Decimal.
- `+`, `-`, `*`, `%`: operands and result must both be Integer or both Decimal.
- `/`: Decimal × Decimal → Decimal. Integer division is forbidden; callers must use an explicit
  conversion Component before evaluation.
- Ordered comparisons require equal exact types among Integer, Decimal, String, Date, or Duration.
- Equality and inequality require equal exact types, except any value may be compared with null.
- `and`, `or`, `not` accept Boolean or Unknown and return Boolean or Unknown.
- Date + Duration and Duration + Date return Date only when the duration is a whole number of days.
- Date - Duration returns Date only for whole-day duration.
- Date - Date returns Duration measured in whole days.
- Duration ± Duration returns Duration; Duration multiplied by Integer returns Duration.
- No other implicit widening, conversion, parsing, optional unwrapping, unit conversion, or
  operator overload is permitted.

Duration is a signed int64 count of seconds. Literal unit multiplication and duration arithmetic
must remain within int64 seconds or fail with overflow.

## Numeric Policy

### Integer

Integer arithmetic is exact signed int64. Every literal, intermediate, and result is range-checked.
Overflow is a deterministic error. Division is not defined for Integer. Integer modulo follows
Euclidean modulo with a result having the divisor's sign; a zero divisor is an error.

### Decimal128

Decimal uses the IEEE 754 Decimal128 interchange semantics represented in software:

- precision: 34 significant decimal digits;
- rounding: round-half-even (banker's rounding);
- adjusted exponent range: `-6143` through `+6144`;
- clamp: enabled;
- traps: InvalidOperation, DivisionByZero, Overflow, and non-finite result;
- subnormal finite results are permitted and rounded under the same context;
- NaN, signaling NaN, positive infinity, and negative infinity are never values.

Every Decimal literal and operation executes under this pinned context. Decimal comparison is
numeric and exact after context-valid construction. Numerically equal representations compare
equal and canonicalize to the same value. Negative zero canonicalizes to zero.

Division or modulo by numeric zero is a deterministic runtime error. A statically constant zero
divisor is a compile-time error.

## Three-Valued Logic

Null represents Unknown. Unknown is contagious unless handled by `is_null` or `coalesce`.

```text
not true     = false
not false    = true
not unknown  = unknown

false and X  = false       (X is not evaluated)
true and X   = X
unknown and false = false
unknown and true  = unknown
unknown and unknown = unknown

true or X    = true        (X is not evaluated)
false or X   = X
unknown or true = true
unknown or false = unknown
unknown or unknown = unknown
```

`unknown == unknown` is true; `unknown != unknown` is false. Comparing exactly one Unknown operand
with a non-Unknown using `==` yields false and using `!=` yields true. Ordered comparison,
arithmetic, date arithmetic, normalization, and numeric functions with any Unknown operand return
Unknown unless the function contract below says otherwise.

Short-circuiting is mandatory. A skipped operand consumes no evaluation steps, produces no error,
and contributes no evaluated-node trace entry.

## Built-In Functions

Only the following exact names and signatures exist. All are pure. No user-defined functions or
overloads outside these signatures are permitted.

### Null handling

- `is_null(T | Unknown) -> Boolean`
- `coalesce(T | Unknown, T) -> T`

`coalesce` evaluates its second argument only when the first is Unknown.

### Scalar numeric

- `abs(Integer) -> Integer`; `abs(Decimal) -> Decimal`
- `round(Decimal, Integer digits = 0) -> Decimal`, round-half-even; `digits` range `[-34, 34]`
- `floor(Decimal) -> Integer`
- `ceil(Decimal) -> Integer`
- `clamp(T value, T lower, T upper) -> T`, for equal exact Integer or Decimal types
- `minmax(Decimal value, Decimal lower, Decimal upper) -> Decimal`

Clamp bounds are inclusive and `lower <= upper` is required. Min-max normalization computes
`(value - lower) / (upper - lower)` without implicit clamping; `lower < upper` is required. Reversed
or equal bounds are deterministic errors.

### Finite aggregation

- `count(List[T]) -> Integer`, including zero for an empty list
- `sum(List[Integer]) -> Integer`; `sum(List[Decimal]) -> Decimal`
- `min(List[T]) -> T`; `max(List[T]) -> T`, for orderable exact T
- `average(List[Decimal]) -> Decimal`
- `mean(List[Decimal]) -> Decimal`, an exact alias of `average`
- `all(List[Boolean | Unknown]) -> Boolean | Unknown`
- `any(List[Boolean | Unknown]) -> Boolean | Unknown`
- `zscore(Decimal value, List[Decimal] fixed_inputs) -> Decimal`

Iteration follows the immutable List's semantic order. Sum of an empty list is the typed zero.
Min, max, average, and mean require at least one item. All of an empty list is true; any of an empty list
is false. Their Unknown semantics are the corresponding repeated three-valued `and`/`or` rules.

Z-score uses the population mean and population standard deviation of `fixed_inputs` under the
pinned Decimal128 context. The list must be non-empty and have nonzero population variance; zero
variance is an error. No live or inferred sample may enter the function.

### Date and Duration

- `add_duration(Date, Duration) -> Date`
- `subtract_duration(Date, Duration) -> Date`

The Duration must be a whole number of days. Results outside ISO dates `0001-01-01` through
`9999-12-31` are errors.

## Validation and Compilation

Compilation has these deterministic phases:

1. UTF-8 and source-length validation;
2. lexical analysis;
3. parsing to the immutable canonical AST;
4. depth and node-count validation;
5. identifier resolution against the supplied immutable type environment;
6. function arity and keyword validation;
7. bottom-up exact type validation;
8. static constant folding and static overflow/divide-by-zero detection;
9. referenced-input collection in lexicographic order;
10. canonical AST serialization and compiled identity derivation.

The compiler may fold a node only when all inputs are literals and doing so yields exactly the
same value or error as runtime evaluation. It cannot reorder user operands because ordering affects
short-circuit trace semantics and error precedence.

`CompiledExpression` is immutable and contains language version, canonical AST, result type,
referenced input names and types, effective resource limits, Decimal policy version, canonical AST
bytes, and expression identity. It contains no callable, code object, environment value, timestamp,
source path, or host-language AST.

Compile once/execute many means one CompiledExpression may be evaluated against multiple immutable
environments matching its pinned input type map. Compilation never captures input values.

## Canonical AST and Serialization

Each AST node is an immutable record with:

- `kind`: closed lowercase node-kind string;
- `type`: exact Strategy Type Reference after compilation;
- `value`: canonical literal/function/operator value when applicable;
- `children`: ordered tuple of child nodes;
- `source_span`: excluded from semantic serialization and identity, retained only for diagnostics.

Closed node kinds are `literal`, `input`, `unary`, `binary`, `call`, `date_literal`, and
`duration_literal`. Operators and function names serialize by the exact canonical spelling in this
document. Literal canonicalization uses normalized Integer, Decimal, Boolean, String, Date,
Duration-seconds, and null representations.

Canonical AST serialization is UTF-8 JSON with lexicographically sorted object keys, compact
separators, no ASCII escaping, ordered child arrays, exact type references, and no unknown fields,
NaN, infinity, source spelling, whitespace, comments, spans, or implementation metadata.

Expression identity is lowercase SHA-256 in namespace `asa.expression`, identity version `v1`,
over canonical JSON containing:

- language version `1.0.0`;
- canonical typed AST;
- exact referenced-input type map sorted by identifier;
- Decimal context and rounding policy;
- effective resource limits;
- function-registry version `1.0.0`;
- type-system version.

Equivalent whitespace and Decimal spellings produce the same identity after canonicalization.
Algebraically equivalent but syntactically different expressions do not generally share identity.

## Resource Limits

V1 limits are fixed and included in compiled identity:

- source: 16,384 UTF-8 bytes;
- AST depth: 64 nodes, with a literal/input root at depth 1;
- AST nodes: 512 before and after constant folding;
- referenced identifiers: 128;
- function arguments: 128;
- evaluation steps: 4,096 evaluated AST nodes;
- input collection length: 1,024 items;
- string literal and input string: 16,384 UTF-8 bytes;
- no recursion or loops;
- no language-level allocation.

Collection length is validated before evaluation. Each visited AST node consumes one step. A
short-circuited node is not visited. Exceeding a limit is a deterministic non-recoverable error.
Limits are not caller-configurable in v1; changing one advances the language version.

## Error Model

Errors are immutable structured values for trace and testing, and evaluation raises the
corresponding deterministic exception. They contain language version, phase, stable code,
canonical AST path when available, source span for diagnostics, and a bounded non-secret message.
They contain no host exception text or stack trace in canonical output.

Compile-time codes include `invalid_utf8`, `source_too_long`, `syntax`, `unknown_identifier`,
`unknown_function`, `arity`, `type`, `integer_overflow`, `decimal_invalid`, `divide_by_zero`,
`limit_depth`, and `limit_nodes`.

Runtime codes include `missing_input`, `input_type`, `integer_overflow`, `decimal_invalid`,
`divide_by_zero`, `null_violation`, `invalid_bounds`, `empty_aggregation`, `invalid_conversion`,
`date_range`, `duration_range`, `collection_limit`, `string_limit`, and `step_limit`.

Errors are not recoverable inside expressions. There is no catch, fallback, retry, partial result,
or warning conversion. Validation reports the first error by compilation phase, then pre-order AST
path, then stable code. Runtime evaluates left-to-right and reports the first error encountered on
the mandatory evaluation path. Short-circuited paths cannot error.

## Evaluation and Trace

Evaluation accepts exactly one CompiledExpression and an immutable, unique-keyed environment. It
first verifies every referenced input exists and has the exact pinned Strategy Type. Extra inputs
are permitted but invisible and excluded from trace and result identity.

The evaluator returns an immutable typed result plus an immutable Expression Trace. Every trace
records:

- expression identity/compile hash;
- referenced input names, exact types, and deterministic value identities;
- output type and deterministic value identity;
- evaluated AST node identities in actual execution order;
- per-node canonical output identity or error code;
- language, function-registry, type-system, Decimal-policy, and resource-limit versions.

Raw sensitive values are not required in the trace; canonical value identities are sufficient.
Source spans, wall-clock timestamps, durations, process/thread data, and skipped nodes are excluded
from semantic trace identity.

## Replay Guarantees

The replay bundle is the CompiledExpression plus exact referenced typed inputs. Given identical
language/function/type-system versions, limits, canonical AST, and inputs:

- compilation produces identical canonical AST bytes and expression identity;
- evaluation produces the identical typed output or identical structured error;
- the evaluated-node sequence and semantic trace are identical;
- host, locale, timezone database, hash seed, process, thread, wall clock, and input enumeration
  order cannot affect the result.

“Identical manifest” means identical semantic expression source after canonical parsing and the
same pinned input type map. Source whitespace does not affect replay identity.

## Security

Expression source is data. The implementation must not call host `eval`, `exec`, compile-to-native
code, import machinery, reflection, attribute lookup, filesystem, network, environment, clock,
random, subprocess, serialization hooks, or dynamic function discovery. The built-in registry is
closed in source and versioned. Plugins cannot add operators or functions in v1.

## Consequences

- Decimal-point “float” syntax is supported but always denotes exact Decimal128, preserving
  ASA-ARCH-003's binary-float prohibition.
- Three-valued logic is explicit and replayable rather than inherited from a host language.
- The grammar is intentionally smaller than Python/JavaScript and cannot embed arbitrary code.
- Fixed resource limits favor safety and deterministic failure over configurability.
- Function and type semantics are public contracts; changes require a new language version and
  Founder-reviewed architecture revision.

## Alternatives Rejected

1. **Validated Python AST as canonical grammar.** Rejected because host-version parsing behavior
   and accepted syntax would become an implicit public dependency.
2. **IEEE binary float.** Rejected because exact source replay and financial decimal policy require
   Decimal128.
3. **Implicit Integer/Decimal widening.** Rejected because the Strategy Type System requires an
   explicit conversion Component.
4. **Two-valued null coercion.** Rejected because it hides missing knowledge; Unknown remains
   explicit.
5. **Calendar months/years in Duration.** Rejected because variable calendar lengths introduce
   semantics not needed by v1.
6. **User/plugin functions.** Rejected because they would alter language vocabulary, safety, and
   replay outside the pinned Core registry.
7. **Caller-configurable limits.** Rejected for v1 because limits affect observable success and
   failure and would fragment replay policy.

## Governance and Continuation

This document is an architecture contract and is Founder-merge-only. It is not eligible for
Amendment 013 delegated merge. STRAT-007 remains blocked until this document reaches `main` by
Founder merge. After merge, Issue #81 may close and STRAT-007 resumes under the existing bounded
SPRINT-002 delegation, followed by STRAT-005, STRAT-008, STRAT-009, STRAT-010, and STRAT-011.

## References

- ASA-ARCH-003: Strategy Composition Architecture
- Strategy Manifest Wire Contract v1
- Strategy Component Framework v1
- Strategy Type System v1
- GitHub Issue #81
- Architecture Constitution, Laws 3, 4, 6, 7, 9, and 10
- Accepted GOV-AMD-001 Amendment 013
