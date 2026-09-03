# PRODUCT-STATE-TRUTH-001 — PST-01 truth reconciliation

Captured against production deployment
`b88b0fb0e1d768f4040067c9e70c9c1fa96a413c` on 2026-09-03. This is a
read-only reconciliation of latest-state persistence and the Agent Data API;
it is not a screening run report.

## Identity capture

| Field | Value |
|---|---|
| reconciliation started | 2026-09-03T17:54:46Z |
| database query | 2026-09-03T17:54:46.663936Z |
| API fetch completed | 2026-09-03T17:55:04Z |
| persisted latest-state rows | 1,525 |
| API envelope total | 1,525 on every page |
| API offsets | 0, 500, 1,000, 1,500 |
| API page sizes | 500, 500, 500, 25 |
| unique API identities | 1,525 |
| identity checksum | MD5 `3020b8435af9b5909307fc966ddd7079` |

The checksum input is the comma-joined, lexically sorted set of
`signal_id:symbol` identities. The database and API page union produced the
same checksum. The page union contained no duplicate or missing identity.

## Exact latest-state counts

| Signal | Total | `missing_data` | `no_signal` | `pass` |
|---|---:|---:|---:|---:|
| `earnings_calendar` | 503 | 414 | 88 | 1 |
| `forward_factor` | 511 | 158 | 353 | 0 |
| `skew_momentum` | 511 | 19 | 492 | 0 |
| **All** | **1,525** | **591** | **933** | **1** |

The per-signal API surfaces use the same repository and pagination contract.
Their expected totals are therefore 503, 511, and 511 respectively; consumers
must traverse the second page for the latter two signals.

The eight additional Forward Factor and Skew Momentum identities are retained
latest-state rows outside the current 503-member S&P snapshot. Persistence is
latest-state authority and does not silently delete untouched identities when
a bounded cohort runs.

## Artifact semantics

- `asa.scheduled_screening` JSON/log summaries are **bounded run-cohort
  reports**. A `90/90` result means one 30-subject, three-strategy scheduled
  cohort completed. It does not mean the latest-state table has 90 rows.
- `GET /api/v1/screening` and its signal-specific forms are **current
  latest-state snapshots**, explicitly paginated. Their envelope `total`
  describes the filtered latest-state set; `results.length` describes only the
  returned page.
- Recent production proofs used both artifact types where stated: Railway cron
  output proved bounded execution; token-authenticated API/readiness queries
  proved latest-state and downstream artifacts. Neither summary may inherit
  the other's label.

## Defect boundary

The production persistence set is complete for the rows ASA currently owns,
and the API exposes all of it without identity loss when all pages are joined.
No second persistence or API pagination defect was found.

The proven defect is product-surface-only:

1. `asa/ui/static/api-client.js` requests only offset 0 with limit 500.
2. `asa/ui/static/app.js` discards the authoritative envelope `total`.
3. UI summaries and filters operate on that one page without declaring their
   partial scope.
4. `asa/ui/static/render.js` labels `results.length` as `Persisted rows`.
5. Repository ordering places the 503 Earnings rows first, so the page is 500
   Earnings identities and later strategies are silently starved.

PST-02 must preserve the API contract and exhaustively traverse this bounded
latest-state dataset while rejecting an incompatible multi-page read. Raising
`MAX_LIMIT` is neither necessary nor authorized.

