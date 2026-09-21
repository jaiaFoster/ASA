# DATA-RELIABILITY-001 — REL-03 earnings readiness

Root cause: Forward Factor intentionally treats absent optional earnings
evidence as neutral for its frozen mathematical signal, but the same boolean
was exposed as `earnings_exclusion_gate=true`. That collapsed “unknown” into
apparent clearance and allowed execution-readiness projection to resolve exact
legs despite unconfirmed earnings state.

Correction: signal evaluation and execution readiness are now separate facts.
The frozen Forward Factor signal remains unchanged, while strategy-owned
readiness records one of:

- `confirmed_outside_window`
- `confirmed_inside_window`
- `unknown_unconfirmed`
- `stale_unusable`

The status is exposed as `decision.earnings_clearance`. Unknown/stale evidence
adds a typed warning and produces an `UNKNOWN` execution assessment; confirmed
inside-window evidence produces `NOT_CONSTRUCTIBLE`; only confirmed-outside
evidence may resolve exact intended legs. No provider, scraper, threshold,
formula, or strategy-local acquisition was added.
