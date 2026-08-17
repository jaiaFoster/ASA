# UNIVERSE-001 / UNI-01 — Membership and Scale Preflight

## Decision and membership

- Target: S&P 500 first. Russell 2000 remains blocked until S&P 500 passes.
- Founder-authorized source override: [Wikipedia — List of S&P 500 companies](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies).
- Captured revision: `1369213082`, published `2026-08-13T15:09:18Z`.
- Effective date: `2026-08-13`.
- Membership: 503 unique symbols.
- Artifact: `screening/universe_snapshots/sp500-2026-08-13.json`.
- No paid license, trial, alternate membership merge, or historical reconstruction.

The existing opaque canonical identity `CanonicalInstrumentIdentity("symbol", symbol)`
represents every captured member, including dotted multi-class symbols such as `BRK.B`.
No parallel instrument identity or new domain contract is required. The internal membership
snapshot adds only source/revision/effective-date provenance.

## Production-equivalent load measurement

Method: the actual `asa.scheduled_screening.run_scheduled_refresh` composition and all three
production strategies, with external transport replaced by the established deterministic
multi-capability fixture provider. Each cohort used the first N symbol-sorted members. No runtime,
strategy, acquisition, or budget behavior was mocked out. Durations are local diagnostic values,
not performance guarantees.

| Subjects | Strategy pairs | Provider calls | Quote | Bars | Earnings | Option-chain | Duration | ASA failures |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | 90 | 270 | 30 | 60 | 30 | 150 | 2.365s | 0 |
| 100 | 300 | 900 | 100 | 200 | 100 | 500 | 7.900s | 0 |
| 250 | 750 | 2,250 | 250 | 500 | 250 | 1,250 | 19.350s | 0 |
| 503 | 1,509 | 4,527 | 503 | 1,006 | 503 | 2,515 | 38.874s | 0 |

All subjects completed and were evaluated/classified. There were no quota failures, preparation
failures, deferred subjects, or ASA-caused failures under fixture capacity.

## First proven bottleneck

The current topology performs nine provider calls per raw member, including five option-chain
calls. Therefore expensive work grows exactly with raw membership: 150 option calls at 30 symbols,
2,515 at 503. This violates UNI-02's required outcome that expensive acquisition track viable
candidates better than raw membership.

Owner: generic subject planning/acquisition staging (`screening/subject_planning.py` and the
strategy requirement/expansion seam), not membership, provider normalization, or strategy scoring.

UNI-02 should reproduce this baseline and introduce the smallest generic staged-acquisition
correction using existing declared requirements and sealed knowledge. It must retain 30-symbol
production behavior as the regression control and must not encode strategy-ID branches or loosen
strategy policy.
