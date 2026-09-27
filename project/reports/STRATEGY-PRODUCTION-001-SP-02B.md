# STRATEGY-PRODUCTION-001 — SP-02B

Primary ticket: `SP-02B` — GXZ event-volatility production strategy.

## Outcome

`event_vol_gxz_preea_straddle_to_expiry@1.0.0-research` is registered through
the universal subject-first runtime and scheduled across the canonical
single-name production cohort. It declares quote, earnings, trading-calendar,
and option-chain requirements; uses generic P03 straddles; and projects exact
contract identities and non-unit quantities through the generic execution
assessment/trade-proposal path.

The source gates and closeout assumptions are identity-bearing in the manifest.
Selection is deterministic: first expiry after earnings in the literal 4–10
calendar-day entry window, all qualifying same-strike call/put pairs,
delta-neutral within-pair quantities, and `call volume + put volume` weighting
across pairs (`RA-EV-01`). `DF-GXZ-PAIR-VOLUME@1.0.0` owns that reusable
calculation. The manifest graph owns financial-gate composition and the frozen
entry-session verdict precedence. Any potentially qualifying pair with unknown
required evidence makes the all-pair decision UNKNOWN. PASS/FAIL/UNKNOWN/NO_ACTION
remain distinct.

## Truthful live deferral

Current enabled production providers do not publish the canonical
`TRADING_CALENDAR_V1` range required to prove `session(day0,-3)`. The strategy
therefore returns the typed blocker `G_GXZ_ENTRY_SESSION_UNKNOWN`; it does not
approximate holidays with weekdays, add an undeclared provider, or silently
weaken the entry rule. Registry, scheduling, capability attempts for available
evidence, persistence, generic product projection, tracking identity, and
outcome compatibility are live while this explicit data limitation remains.

## Verification

- Exact-pair, weighting, truth-table, manifest/contract, and generic trade
  proposal tests: green.
- Strategy/runtime/scheduler/architecture integration: `1477 passed`.
- Ruff and mypy over changed strategy/runtime scope: green.
- Full repository suite: `3837 passed, 50 skipped`.
- Lean integrity, entrypoint, and pre-push validation: green.
- CI evidence is recorded on the implementation PR.
