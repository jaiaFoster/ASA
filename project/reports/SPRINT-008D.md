# SPRINT-008D — Final Report

Status: All seven enumerated tickets merged. **Three Founder actions remain outstanding**
before this sprint's own `definition_of_done` is fully satisfied — see Section 12. Requesting
Founder review now; final closure follows once those three actions land.

Sprint reference: `docs/sprints/SPRINT-008D.yaml`
Governance: Amendment 013 Founder Sprint Delegation (`GOV-010`)
Repository commit at report time: `fdbfa00` (`main`)

## 1. Sprint summary

SPRINT-008D was authorized as the bridge between SPRINT-008's deployed-but-empty API and
SPRINT-009's product-feature work: activate the API for real external consumers, and give it a
real, populated, operationally-sound production screening universe. Phase 1 (API Activation)
found and fixed a genuine production outage — the entire new API surface was 404ing for every
caller because `ASA_AGENT_API_TOKEN` had never actually been set on the Railway service, despite
being documented as required. Phase 2 (Screening Productionization) defined an initial 12-pair
production universe, validated provider quality (including a reported Finnhub issue), built the
scheduled execution workflow to populate that universe, defined its cache/freshness policy, and
evaluated (and declined, for now) expanding the underlying symbol bound.

Every ticket in this sprint completed its own investigation, code, and documentation work and is
merged. What remains is not implementation — it is a small number of actions on live
infrastructure that only the Founder can complete, because they require either a secret value
this agent deliberately never saw, or a container-execution capability this agent's available
tooling does not expose. Each is called out precisely, with an exact command, in Section 12.

## 2. Completed tickets

| Ticket | What it did |
|---|---|
| ACT-001 | Root-caused the "authenticated 404" usability issue to a missing `ASA_AGENT_API_TOKEN` on the production service (not a code defect — every relevant code path already had passing test coverage). Fixed it: generated and set a new sealed token via Railway's own tooling, redeployed, verified auth is still correctly enforced. |
| ACT-002 | Wrote and validated a bootstrap guide for a brand-new deployment, backed by a permanent test exercising the exact first-run sequence against a genuinely empty repository. |
| PROD-001 | Defined the initial production universe: `forward_factor` and `skew_momentum` × the full six-symbol `APPROVED_LIVE_UNIVERSE` (12 pairs), justified by a direct provider-capability audit. Deferred `earnings_calendar` pending provider validation. |
| PROD-004 | Investigated the Finnhub authorization issue (most likely an entitlement/plan-tier gap, not a bad credential); confirmed provider capability routing and fallback behavior are correct and already well-tested; found and documented (without fixing) a real gap in the public capabilities catalog's declared data requirements. |
| PROD-002 | Built `asa/scheduled_screening.py`, the scheduled execution workflow, reusing `screening.service.refresh()` directly. Documented the recommended Railway Cron scheduling mechanism. The first actual production run is pending Founder action (Section 12). |
| PROD-003 | Defined the cache and freshness policy: `screening_state` already functions as the cache (no new layer needed); recommended a once-daily scheduling cadence with explicit request-budget and signal-relevance justification. |
| PROD-005 | Evaluated refresh-universe expansion; recommended against expanding now (no real usage data yet, provider capacity is not the constraint); recorded explicit criteria for a future evaluation. Fixed a small consistency gap in PROD-002's own code along the way. |

## 3. Delegated, merged pull requests

| PR | Merged (UTC) | Title |
|---|---|---|
| [#196](https://github.com/jaiaFoster/ASA/pull/196) | 2026-07-23T14:58:14Z | GOV-010: activate SPRINT-008D |
| [#197](https://github.com/jaiaFoster/ASA/pull/197) | 2026-07-23T15:38:56Z | ACT-001: API activation diagnostics — root cause found and fixed |
| [#198](https://github.com/jaiaFoster/ASA/pull/198) | 2026-07-23T15:42:58Z | ACT-002: bootstrap guide and first-run validation |
| [#199](https://github.com/jaiaFoster/ASA/pull/199) | 2026-07-23T15:46:37Z | PROD-001: production screening universe definition |
| [#200](https://github.com/jaiaFoster/ASA/pull/200) | 2026-07-23T15:52:53Z | PROD-004: provider quality validation |
| [#201](https://github.com/jaiaFoster/ASA/pull/201) | 2026-07-23T15:59:44Z | PROD-002: scheduled screening execution and persistence (code) |
| [#202](https://github.com/jaiaFoster/ASA/pull/202) | 2026-07-23T16:13:03Z | PROD-002: production run report — blocked on tooling, action requested |
| [#203](https://github.com/jaiaFoster/ASA/pull/203) | 2026-07-23T16:16:05Z | PROD-003: cache and freshness policy |
| [#204](https://github.com/jaiaFoster/ASA/pull/204) | 2026-07-23T16:19:35Z | PROD-005: refresh universe expansion strategy |

`#196` (the activation) was Founder-merged directly, per Amendment 013's rule that
activation/rescope files are never delegate-merged. Every other PR was self-verified against its
ticket's required gates and merged under the `GOV-010` delegation.

## 4. API activation findings and resolution

Full detail: `project/reports/SPRINT-008D-API-ACTIVATION.md`.

**Root cause**: `ASA_AGENT_API_TOKEN` was never set on the production Railway service, even
though API-006 (SPRINT-008) documented that it must be. `build_agent_authorizer` fails closed to
404 the instant the token is unconfigured, before it even inspects the request header — so every
request to the new surface was guaranteed to 404 regardless of caller behavior. Confirmed with
real evidence: production HTTP proxy logs from the reported beta-testing window, cross-referenced
against a read-only variable-name check (never values) of the live service, plus the contrast
that a *different* token-gated endpoint (`/ops/market-data/validate`, using a token that *was*
configured) succeeded in the same window.

**Fix**: a new sealed token was generated server-side by Railway's own tooling (~258 bits
entropy, never seen by this agent) and set on the production service, followed by a redeploy.
Post-fix verification confirmed the redeploy succeeded and that unauthenticated/wrong-token
requests still correctly 404 — the fix did not accidentally open the endpoint. **Final
confirmation that the correct token itself succeeds is outstanding** (Section 12.1).

No code defect was found anywhere in the authentication or empty-state-handling logic — every
code path involved already had passing test coverage before this investigation began. A
first-run bootstrap guide and permanent test (ACT-002) were added to make this distinction (auth
failure vs. empty state) explicit for the next external consumer.

## 5. Screening universe definition and rationale

Full detail: `project/reports/SPRINT-008D-SCREENING-UNIVERSE.md`.

Initial production universe: `forward_factor` × {AAPL, MSFT, NVDA, AMD, SPY, QQQ} and
`skew_momentum` × the same six symbols — 12 pairs, the full existing `APPROVED_LIVE_UNIVERSE`
for both signals. Justified by a direct data-requirement audit: no enabled provider other than
Tradier supplies `option_chain_v1`, which every registered signal requires. `earnings_calendar`
is deliberately deferred — it additionally needs `earnings_calendar_v1` (Finnhub or Alpha
Vantage), and PROD-004's Finnhub investigation was still pending confirmation at the time this
universe was defined.

## 6. Provider validation results

Full detail: `project/reports/SPRINT-008D-PROVIDER-VALIDATION.md`.

Finnhub's most likely failure mode, based on its own error-classification code
(`market_data/finnhub.py`) and Finnhub's publicly documented API tiers, is an entitlement/plan
gap on the earnings-calendar endpoint — not a bad credential. This is a hypothesis pending one
Founder-run live check (Section 12.2). Provider capability routing and fallback behavior were
both confirmed correct and already well-tested: `CapabilityFulfillmentService` tries providers in
priority order (alphabetical by `provider_id` for `earnings_calendar_v1`, meaning Alpha Vantage
is tried before Finnhub) and falls back on *any* failure type, not only "unsupported" — so a
Finnhub-specific problem likely does not block `earnings_calendar` entirely, pending confirmation
that Alpha Vantage itself is healthy.

One real, minor defect was found and documented, not fixed: all three registered signals
actually require `real_time_quote_v1` for live acquisition, but none declares it in
`screening/registry.py`'s public metadata — the `GET /api/v1/capabilities` catalog currently
underclaims what a live refresh needs. No functional impact today (Tradier alone covers both
capabilities for the current universe). Recommended for a future ticket (Section 13).

## 7. Production screening run results

Full detail: `project/reports/SPRINT-008D-PRODUCTION-SCREENING.md`.

`asa/scheduled_screening.py` is built, unit-tested (4 tests against injected fakes, no live
database or network required), and merged. **It has not yet been executed against production.**
This agent's available Railway tooling could set and generate sealed variables but could not
execute a one-off command inside the live container — every attempt failed with a connection
error from the tooling itself, across multiple retries and differently-worded requests. A
precise `railway run` command is provided for the Founder to complete this (Section 12.3). The
recommended ongoing scheduling mechanism (a second, lightweight Railway service with a Cron
Schedule) is documented but intentionally not configured, per explicit direction to leave that
setup to the Founder.

## 8. Cache and freshness policy summary

Full detail: `docs/screening/cache-lifecycle.md`.

`screening_state` itself already has a cache's lifecycle (always-latest via upsert, reads never
compute) — no second cache layer was added or is needed. Recommended scheduling cadence: once
daily, before market open, justified by these signals' lack of intraday urgency (no execution
surface exists) and by request-budget math (~30-50 requests per full run against a
100-request-per-pair ceiling — a shorter cadence would spend budget without a corresponding
benefit). One optimization (sharing option-chain fetches between `forward_factor` and
`skew_momentum`) was considered and explicitly rejected as not worth the coordination complexity
for the request savings involved. This policy's estimates are derived from code defaults and
local test runs, not yet real production timing — flagged as its own revisit trigger once
Section 7's production run history exists.

## 9. Refresh universe expansion recommendation

Full detail: `project/reports/SPRINT-008D-REFRESH-UNIVERSE-EXPANSION.md`.

**Do not expand `APPROVED_LIVE_UNIVERSE` now.** Provider capacity is explicitly confirmed not to
be the constraint (comfortable headroom exists); the actual reason is that no real production
usage data exists yet to ground an expansion decision, and the bound itself carries Founder-level
approval weight from its SPRINT-007 origin that a code-level estimate alone shouldn't override.
Explicit criteria are recorded for a future evaluation: a real PROD-002 run history as the
trigger, the same liquidity bar PROD-001 established, incremental rather than wholesale
expansion, and an unchanged Founder approval path. Both existing provider safety guarantees (the
fixture force-disable, the per-pair budget ceiling) were confirmed untouched.

## 10. Validation results

Current state, verified on `main` at commit `fdbfa00`:

```text
PYTHONPATH=. python -m pytest tests/ -q --ignore=tests/pos --ignore=tests/deployment_observer
  1722 passed, 17 skipped

PYTHONPATH=. python -m pytest tests/asa/test_boundaries.py -q
  5 passed

ruff check asa tests/asa
  All checks passed!

mypy asa
  Success: no issues found in 39 source files
```

Every required gate from `docs/sprints/SPRINT-008D.yaml`'s own
`validation.required_before_every_delegated_merge` list passed on every delegate-merged PR in
this sprint before merge. The `sprint_level` validation items
(`successful_railway_deployment_confirmed_after_PROD_002`,
`populated_screening_database_confirmed_via_the_public_api`,
`successful_external_style_ai_agent_validation_re_run_against_populated_data`) are gated on
Section 12's outstanding Founder actions and are not yet satisfied — recorded honestly here
rather than marked complete prematurely.

## 11. Discovered and resolved defects

| Defect | Discovered during | Resolution |
|---|---|---|
| `ASA_AGENT_API_TOKEN` never set on production, causing every new-surface request to 404 | ACT-001 | Fixed: new sealed token generated and set, redeployed, partially verified (Section 12.1 completes it) |
| `asa/scheduled_screening.py` hardcoded its own copy of the six approved symbols instead of importing `APPROVED_LIVE_UNIVERSE` | PROD-005 | Fixed: now references the constant directly |
| Public `/api/v1/capabilities` catalog omits `real_time_quote_v1` from all three signals' declared requirements, despite every live adapter needing it | PROD-004 | Documented, not fixed — recommended for a future ticket (Section 13) |
| Apparent Railway deploy-command drift between a config-query tool's report and `railway.json` | ACT-001 | Investigated and ruled out — the config-query tool's report was not authoritative; the actual build log confirmed `railway.json` is correctly used |

## 12. Outstanding Founder actions (blocking full sprint closure)

Three specific, precise actions remain, each documented with an exact command in its own
ticket-level report:

### 12.1 Confirm the new agent API token works (ACT-001)

Retrieve `ASA_AGENT_API_TOKEN` from the Railway dashboard and confirm:

```bash
curl -sS https://asa-production-b2c4.up.railway.app/api/v1/capabilities \
  -H "Authorization: Bearer <the token>"
```

returns `200` with the three-signal catalog.

### 12.2 Run the Finnhub diagnostic (PROD-004)

```bash
curl -sS -X POST https://asa-production-b2c4.up.railway.app/ops/market-data/validate \
  -H "Authorization: Bearer $ASA_OPERATIONS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"providers": ["finnhub"]}'
```

Share the `entitlement_status`/`normalized_check_status` for the `earnings_calendar_v1` check —
this response is secret-free by the endpoint's own design.

### 12.3 Run the first production screening run (PROD-002)

```bash
railway run --service ASA --environment production python -m asa.scheduled_screening --json
```

Share the resulting JSON output, then confirm via
`GET https://asa-production-b2c4.up.railway.app/api/v1/screening` (with the token from 12.1) that
`"total"` is populated.

## 13. Remaining non-blocking issues

- `real_time_quote_v1` is missing from all three signals' declared `required_capabilities` in
  `screening/registry.py`, understating what a live refresh actually needs in the public
  capabilities catalog. No functional impact on the current universe. Recommended fix: add it to
  `screening/adapters.py`'s `TARGET_STRATEGY_DEFINITIONS`, as its own reviewed ticket.
- Issue #147 (no dedicated CI coverage for `tests/screening/` or root-level `mypy`), carried
  forward unresolved from SPRINT-008's own final report — still open, still accurate.
- Ongoing scheduling is documented (`project/reports/SPRINT-008D-PRODUCTION-SCREENING.md`) but
  not yet configured — a second Railway Cron service is recommended, left for the Founder to set
  up when ready.

## 14. Recommendations for SPRINT-009

1. Complete the three outstanding Founder actions (Section 12) before beginning SPRINT-009 —
   they are the actual completion of this sprint's own `definition_of_done`, not optional
   follow-ups.
2. Once 12.3 is complete and the first production run's real timing/request data exists, revisit
   `docs/screening/cache-lifecycle.md`'s freshness cadence and PROD-005's expansion criteria with
   real evidence instead of code-level estimates.
3. Set up the recommended Railway Cron service for ongoing scheduled execution
   (`project/reports/SPRINT-008D-PRODUCTION-SCREENING.md`, Section 4) — without it, the universe
   populated by 12.3 will not stay fresh on its own.
4. Fix the `real_time_quote_v1` capability-declaration gap (Section 13) as a small, standalone
   ticket before it causes confusion for an external integrator relying on the capabilities
   catalog being complete.
5. Once `earnings_calendar` is unblocked by 12.2's confirmation, add it to the production universe
   (PROD-001, Section 6's own documented signal-expansion axis) — no new universe definition work
   needed, just execution.
6. As originally planned, SPRINT-009 itself should now focus on product capability (richer
   signals, Forward Factor maturation, recommendation intelligence, portfolio analytics) with
   infrastructure work limited to defects or targeted improvements — this sprint was explicitly
   the bridge to get there.

## 15. Founder verification requested

Per this sprint's own `definition_of_done`: every enumerated ticket is merged, every required
gate passed on every merge, and this report is now committed. Three specific, precise actions
(Section 12) remain before every item in that `definition_of_done` is satisfied. Requesting
Founder review of this report and completion of Section 12's actions; final SPRINT-008D closure
and SPRINT-009 authorization should follow once they're done.
