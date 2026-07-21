# ASA Expression Language Runtime Contract v1

Status: implementation contract for STRAT-007. Normative semantics are frozen in
`architecture/ASA-ARCH-004-Expression-Language.md`.

The runtime exposes `compile_expression(source, input_types)` and
`evaluate_expression(compiled, inputs)`. Compilation produces an immutable typed AST,
canonical AST bytes, an `asa.expression/v1` content identity, referenced input types,
and fixed resource limits. Evaluation accepts immutable typed values and returns an
immutable value plus deterministic trace. The compiled object is safe to evaluate
repeatedly and contains no mutable execution state.

The implementation uses a closed expression-only parser. It does not delegate syntax or
execution to Python `ast`, `eval`, or `exec`. Identifiers can only reference declared
inputs. Functions come from the pinned pure-function registry; imports, reflection,
I/O, networking, current time, randomness, assignment, loops, and recursion have no
grammar or runtime entry point.

Numeric execution uses signed int64 with checked overflow and a 34-digit Decimal context
with half-even rounding. Binary floats are not accepted. Dates are ISO-8601 dates and
durations are fixed `timedelta` values; months, years, timezone conversion, and daylight
savings behavior are absent. Null is the singleton `Unknown` value and logical operators
use deterministic three-valued short-circuit semantics.

Resource policy is part of expression identity: source bytes 16,384; AST depth 64; AST
nodes 512; identifiers 128; function arguments 128; evaluation steps 4,096; collection
length 1,024; string bytes 16,384. Changing these values or the language, function
registry, type-system, Decimal, or AST policy changes the resulting identity.
