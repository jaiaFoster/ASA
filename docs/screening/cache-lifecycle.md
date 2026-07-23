# Screening State — Cache & Freshness Policy

SPRINT-008D/PROD-003. Applies to every row in the `screening_state` table (Postgres) and
therefore to every result `GET /api/v1/screening*` returns.

## There is no separate cache — `screening_state` already is one

`screening_state` stores only the latest evaluated result per `(signal_id, symbol)` pair —
`PostgresScreeningStateRepository.upsert()` is `ON CONFLICT (signal_id, symbol) DO UPDATE`, never
an insert-only history table (API-002, SPRINT-008). That single property already makes the table
function as a cache: a read never recomputes anything (`screening.service.get_state()` is a pure
repository read — SPRINT-008's own `architecture_principles`), and a write always replaces
whatever was there before. No additional caching layer, cache service, or cache invalidation
mechanism was added or is needed for this — the existing repository already has exactly the
lifecycle a cache needs, and introducing a second cache in front of it would only add a second,
redundant source of truth to keep consistent with the first.

## Freshness is reported, never decided, by the API

Every screening result carries `updated_at` and a server-computed `age_seconds`
(`TimestampedResource.age_seconds_since`, `asa/api/agent_models.py`). The API deliberately never
adds an opinion on top of that number — no `is_stale` field, no staleness threshold baked into
any response (`docs/api/agent-api-operations.md`'s own `api_reports_facts_not_policy` principle,
unchanged by this ticket). What this document defines is the **production scheduling policy**
that determines how large `age_seconds` typically gets before a fresh value replaces it — an
operational decision, not a new API contract.

## The refresh cadence target

**Once per day**, before U.S. market open (per PROD-002's own recommendation,
`project/reports/SPRINT-008D-PRODUCTION-SCREENING.md`), for every pair in the current production
universe (PROD-001: `forward_factor` and `skew_momentum`, 12 pairs total). This means, under
normal operation, `age_seconds` on any given result stays roughly within one day plus whatever
scheduling jitter the chosen trigger mechanism has — there is no code-level guarantee of this
(the API itself is cadence-agnostic by design), only an operational one.

**Why daily is enough, not merely convenient**: the inputs these three signals depend on — option
chain structure, implied-volatility skew, forward-factor calendar spreads — do not carry the kind
of intraday urgency a live-trading system's price feed would. `docs/api/agent-api-operations.md`
already documents that this API has no live-trading or execution surface (`SPRINT-008D`'s own
`bounded_scope.out`); a screening signal meant to surface candidate opportunities for further
review does not need sub-daily refresh to remain useful, and a shorter cadence would only consume
provider request budget without a corresponding benefit to what the signal is for.

## Why this also minimizes unnecessary provider requests

Each `(signal, symbol)` pair's live acquisition issues a small, fixed number of provider requests
(a spot quote, an expiration lookup, one or more option-chain fetches — `docs/api/agent-api-operations.md`
Section "Rate limiting and request budgets"). At 12 pairs and roughly 2-4 requests each, one full
scheduled run consumes on the order of 30-50 provider requests — trivial against the existing
per-pair ceiling (`market_data.config.RequestBudgetConfig`'s own default of 100 requests per
provider per run, applied fresh per pair, never shared across pairs — `market_data/config.py`).
Running less often than daily would save a negligible amount of request budget while directly
increasing `age_seconds`; running more often would consume more budget for data that, per the
reasoning above, does not need it. Daily is the point where neither side is being wasted.

A different, more aggressive optimization was considered and explicitly **not** implemented:
sharing a single acquired option chain across `forward_factor` and `skew_momentum` for the same
symbol, since both need `option_chain_v1` data for the same underlying. This was rejected for
this ticket — the two signals request different expirations and strikes internally
(`screening/live_adapters.py`: `forward_factor` needs a front/back calendar pair,
`skew_momentum` needs only the nearest expiration), so a shared-chain optimization would require
either over-fetching for both signals or a new coordination layer between them, exactly the kind
of new architecture this sprint's own `quality.avoid` (`major_architectural_refactoring`,
`duplicate_execution_paths`) rules out for a savings this small (2 provider requests out of
roughly 40 per run).

## Determinism is unaffected

This policy does not change response determinism (`tests/asa/test_ai_agent_workflow.py`'s own
finding: an unchanged repository row produces identical field values on repeated reads, `age_seconds`
aside). Refresh cadence only changes *how often* a row's `updated_at` moves forward — never
whether reads are deterministic in between.

## Revisit this policy when

- PROD-002's actual production run history exists (execution timing, real request counts per
  run) — this document's request-budget estimates above are derived from code-level defaults and
  local test runs, not yet from real production timing, since the first production run had not
  executed at the time this was written (`project/reports/SPRINT-008D-PRODUCTION-SCREENING.md`).
- The screening universe (PROD-001) or the refresh universe (PROD-005) expands meaningfully — a
  materially larger pair count could change the request-budget-per-run math enough to warrant a
  different cadence.
