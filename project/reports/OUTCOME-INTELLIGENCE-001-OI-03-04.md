# OUTCOME-INTELLIGENCE-001 — OI-03 collector and OI-04 ledger

Baseline: `main@d52146f` (OI-02 model merged in #492)
Authority: Architect decision APPROVED-WITH-AMENDMENTS
(`OUTCOME-INTELLIGENCE-001-OI-02-04-ARCHITECT-DECISION.md`), risk class R3.

## ⚠ Merge requires the Founder

Production deploys run `alembic upgrade head` automatically (`Dockerfile`,
`railway.json`), and `main` auto-deploys. Merging this PR therefore **applies
migration `0019` to production**. Deployment and migration application are
Founder-only under the program and the Architect decision, so this PR is
left for a Founder merge. The migration is additive (one new table); its
`downgrade` destroys non-regenerable forward evidence and must never be run
in production without Founder direction.

## Delivered (per the binding amendments)

| Concern | Implementation |
|---|---|
| Record | `asa/contracts/forward_outcome.py` — invariants: only `observed` carries evidence time; missed/unobservable carry no values; mark and P&L together or absent |
| Ports | `asa/application/ports/forward_outcomes.py` — repository, evidence source, `ForwardOutcomeConflictError` |
| Collector | `asa/application/forward_outcomes.py` — frozen proposal only; evidence-time window; `missed` finality; `not_observable_before_tracking`; per-tick subject cap; no backfill |
| Market data | `asa/integrations/forward_outcome_market_data.py` — own `outcome-collection:` plan over `build_shared_market_data_access`; quote + per-frozen-expiration chain only; no broker |
| Ledger | migration `0019` + `asa/integrations/forward_outcome_postgres.py` — PK (candidate, horizon), FK `ON DELETE RESTRICT`, status/time CHECKs, insert-then-read-back; identical content idempotent, different content raises; no update/delete path |
| Entry | `asa/scheduled_outcomes.py`, called last and isolated from `scheduled_screening.main`; screening JSON report unchanged; also `python -m asa.scheduled_outcomes` |
| API | `GET /api/v1/portfolio/tracked-candidates/{id}/outcomes` — recorded rows plus computed, unstored `pending` rows; 404 for unknown; basis `paper_modeled_not_brokerage_fill; user_tracked_corpus` |

## Proof

- 10 collector/ledger/API tests, including a real-Postgres test (append-only,
  idempotent replay, conflict raises, RESTRICT blocks candidate deletion).
- Migration upgrade → downgrade → upgrade verified on Postgres 16.
- Full suite with a live test database: 3,618 passed / 2 skipped.
- Scan test: no strategy IDs, no latest-state or readiness reads, no broker
  interfaces in the new modules.

## Corpus disclosure

The corpus is **user-tracked proposals only** (selection bias); OI-05/OI-07
must disclose it. Auto-enrollment needs a separate Architect decision.
