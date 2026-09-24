# OI-02/03/04 Architect Decision: forward outcome ledger

ROLE-ARCH · OUTCOME-INTELLIGENCE-001 · 2026-09-24 · read-only, main @ 3b50f38

**Verdict: APPROVED-WITH-AMENDMENTS.** Sound base; amendments below are binding.

## 1. Facts relied on

- The frozen `resolved_proposal_json`, its identity and `evidence_observed_at` live on `TrackedCandidate` (migration 0018). Stock and legacy candidates carry no canonical proposal.
- Existing append-only tables use `DO NOTHING` and `CASCADE`. Neither is acceptable here.
- `SubjectAcquisitionPlan`, per-expiration `OPTION_CHAIN_V1` requests and `UsEquitySessionCalendar` are all generic.

## 2. Ownership

| Concern | Owner |
|---|---|
| Horizon schedule and mark/P&L computation: pure, no I/O, no strategy IDs | new `strategy_runtime/forward_outcome.py`, beside `trade_proposal`/`option_payoff` |
| `ForwardOutcomeObservation` record | new `asa/contracts/forward_outcome.py` |
| Collector use case plus repository port | `asa/application/forward_outcomes.py`, `asa/application/ports/forward_outcomes.py` |
| Persistence | `asa/integrations/forward_outcome_postgres.py`, migration `0019` |
| Entrypoint | `asa/scheduled_outcomes.py` (own `main`), called last from `scheduled_screening.main` in an isolated `try`. No new cron. `bounded_run_cohort` JSON unchanged. |

## 3. Market-data acquisition

The collector **must not** reuse the screening subject plan or strategy demands, because that couples outcomes to strategy selection. Instead:

- It builds its **own `SubjectAcquisitionPlan`** per subject per tick over `build_shared_market_data_access`. Registry, budgets, rolling windows and attempts are shared, so there is still one authority.
- It issues narrow direct requests only:
  - `REAL_TIME_QUOTE_V1` for the underlying;
  - `OPTION_CHAIN_V1` scoped to each distinct frozen-leg expiration.
- IDs use an `outcome-collection:` namespace.
- A per-tick subject cap applies. Budget exhaustion is a typed failure, retried while the window is open.
- Strategies acquire nothing. Brokers are never called.

## 4. Horizons: generic runtime

Generic, from frozen data only; no strategy-ID branching. Policy `oi-horizons-v1`, anchored at `evidence_observed_at`:

- `d1`, `d5`, `d10`: the close of the Nth full US-equity session after the anchor's session. `next_session_close` folds into `d1`.
- `first_expiration`: the close of the earliest leg expiration. Only with a frozen option proposal; nothing is scheduled after it.

Strategy-declared checkpoints are deferred (manifest change, separate ADR-010 decision).

## 5. Look-ahead prevention (binding invariants)

1. The due time is a pure function of `(anchor, policy_version, frozen legs, calendar)`.
2. Eligibility is judged by the **provider evidence `observed_at`**, never the wall clock. Evidence must fall inside a versioned window around the due close, initially `[close−20m, close+10m]`.
3. The first eligible observation is final. Once the window has passed with nothing eligible, the collector writes `missed`. It never backfills with later data.
4. When a horizon falls due before `tracked_at`, the collector writes `not_observable_before_tracking` for it.
5. The entry reference is only the frozen `resolved_proposal_json`. The collector never reads `universal_screening_state`, `execution_readiness_artifacts` or the latest proposal, and never writes to them.

## 6. Model amendments (OI-02)

- Key `(tracked_candidate_id, horizon_id)`; `observed_at` is a field. Status: `observed`, `missed`, `not_observable_before_tracking`.
- **Midpoint mark:** Σ side × qty × mid × multiplier over the exact frozen legs.
  - Mid needs bid and ask, 0 ≤ bid ≤ ask. Any absent leg makes mark and P&L UNKNOWN with typed per-leg reasons; no partial mark, no Black-Scholes fill-in.
  - Labelled `modeled_midpoint_mark_not_fill`.
- **`first_expiration` mark:** legs expiring that day are valued at intrinsic value from the in-window underlying quote (`terminal_intrinsic_from_observed_underlying`). Surviving legs use their mid.
  - Assignment/pin risk are stated assumptions; a non-equity/ETF root gives UNKNOWN `settlement_style_unknown`.
- **Stocks and legacy candidates:** the collector records the underlying quote only. Modeled P&L is UNKNOWN `no_frozen_structure_entry`.
- MFE/MAE are not stored. Any derived display must say "sampled at horizons", not path extremes.
- Each observation carries the model and horizon policy versions, `due_at`, `collected_at`, the frozen proposal identity, provider/evidence snapshot provenance, and a sha256 `content_identity`.

## 7. Ledger amendments (OI-04)

- Table `forward_outcome_observations`: unique `(tracked_candidate_id, horizon_id)`, FK **`ON DELETE RESTRICT`**, status `CHECK`.
- **Insert behaviour:** insert with `ON CONFLICT DO NOTHING`, then read back. The same `content_identity` is idempotent. A different one raises `ForwardOutcomeConflictError` and is never overwritten.
- No update/delete path exists (tested).
- `GET /api/v1/portfolio/tracked-candidates/{id}/outcomes` is read-only. It returns the frozen identity, the horizon schedule (with computed, unstored `pending` rows), the observations and a basis label. An unknown candidate returns 404. No existing response model changes.
- The migration `downgrade` drops accumulated forward evidence, which cannot be regenerated. Running it in production is a Founder-only destructive action.

## 8. Risk and governance

- **Risk class: R3.** The change adds a new canonical, non-regenerable data set and a production cron path that shares provider budgets with screening.
- R3 process applies; Architect approval is **this document**.
- **ADR-010 final line:** it does not require separate Founder review. The change touches no strategy manifest, contract, graph or existing public contract. The table and endpoint are additive, and the Founder explicitly authorized OI-04's ledger.
- Delegated merge is permitted. Deployment and migration application stay with the Founder.
- **Stop and escalate** if implementation alters an existing table or response schema, needs a manifest field, acquires outside `market_data`, or branches on a strategy ID.

## 9. Out of scope

- Fills, broker P&L and broker calls; prioritization (OI-06); UI (OI-05); BS repricing; stored MFE/MAE; strategy checkpoints; backfill and paid data.
- Auto-enrolling untracked proposals. The user-tracked corpus's selection bias must be disclosed in OI-05/OI-07. A wider enrollment source needs a separate Architect decision.

## 10. Tests required

- Calendar edge cases for the horizon schedule.
- Window rejection, and `missed` finality.
- Mark sign conventions, and UNKNOWN when a leg is absent.
- Replay versus a conflict raising.
- No reads of latest-state tables.
- A scan confirming no strategy-ID literals.
- API 404 and pending rows.
