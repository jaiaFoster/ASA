# TGSM-RUNTIME-001 — S001-05 target decision and ledger

Base: `main@7842c21`. Ticket: S001-05. Assigned Worker:
implementation-worker. Manager stop status: CLEAR.

## Outcome

S001 now projects a deterministic immutable target decision from the complete
S001-04 selection. The strategy-owned policy creates exactly three rational
`1/3` sleeves. A passing selected sector retains its own sleeve; a failing
selected sector routes only that sleeve to the canonical research identity
`research_asset:us_3_month_treasury_total_return`. Passing sleeves are never
reweighted. Unknown trend evidence prevents allocation rather than becoming a
failure or a fabricated defensive target.

Defensive substitution requires an explicit canonical Treasury total-return
fact identity effective no later than the decision. BIL, cash, raw yield, or
another instrument is rejected. The decision effective time is supplied by an
injected trading-session authority and must strictly follow the finalized
decision evidence time. No execution, sizing, leverage, shorting, broker, or
order semantics exist.

Decision identity covers strategy version, decision/effective times, eligible
universe, ranking, targets, exact rational weights, trend states, and evidence
fact identities. Canonical serialization verifies that identity during read.
A generic append-only decision ledger provides idempotent persistence and
provider-free replay; conflicting content under one identity fails closed.

## Evidence and recovery

- Focused S001 target/composition/knowledge plus architecture: 618 passed.
- Strategy runtime, strategies, architecture, screening: 1,436 passed.
- Ruff and mypy: green.
- Pinned tests cover exact thirds, no redistribution, canonical defensive
  evidence, temporal ordering, deterministic identity, tamper rejection,
  immutability, idempotent append, and provider-free replay.
- Recovery is additive: remove the target-decision and decision-ledger modules;
  no existing strategy, persistence table, portfolio, provider, or broker path
  changes.
