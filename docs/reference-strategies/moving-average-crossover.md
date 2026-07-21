# Moving Average Crossover Reference Strategy

The reference strategy is the canonical manifest value
`MOVING_AVERAGE_CROSSOVER_MANIFEST`. It receives short and long moving-average Decimal values as
explicit semantic context, evaluates the closed expression `left >= right`, passes the result
through the portfolio constraint vocabulary, and exposes one Boolean `signal` output.

There is no handwritten strategy evaluator. Core compiles the manifest against the static Core
Component registry and executes it through the ordinary deterministic graph runtime. Replays use
the same manifest, registry, explicit inputs, identities, and lifecycle trace.
