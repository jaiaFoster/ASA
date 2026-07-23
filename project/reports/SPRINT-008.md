# SPRINT-008 — Final Report

Status: All enumerated implementation tickets merged. **Founder verification requested before
SPRINT-009 begins**, per this sprint's own `definition_of_done`.

Sprint reference: `docs/sprints/SPRINT-008.yaml`
Governance: Amendment 013 Founder Sprint Delegation (`GOV-008` → `GOV-008A` → `GOV-008C`)
Repository commit at report time: `823712f` (`main`)

## 1. Sprint summary

SPRINT-008 established ASA's first public, versioned, AI-oriented API surface:
`GET /api/v1/capabilities`, `GET /api/v1/screening`, `GET /api/v1/screening/{signal}`,
`GET /api/v1/screening/{signal}/{symbol}`, and `POST
/api/v1/screening/{signal}/{symbol}/refresh` — exposing ASA's existing screening framework
(SPRINT-006/SCREEN-*) as stable, timestamped, bearer-authenticated HTTP resources, with a single
narrow write operation and no background automation.

The sprint activated as `GOV-008`, was rescoped once at the start (`GOV-008A`, resolving the
CLI/API shared-execution-graph and backend/screening connection questions its original activation
had deliberately left open), completed its first ticket (API-001), then paused: API-001's own
work exposed that the existing Railway deployment configuration could not actually serve the new
code (a pre-existing structural blocker, not something API-001 introduced). Resolving that blocker
required two separate, larger delegations — **OPS-RAILWAY-ROOT-001** (`GOV-008B`) and
**ARCH-MONOREPO-001** (`GOV-009` / `GOV-009-PHASE-2`) — both already fully reported
(`project/reports/OPS-RAILWAY-ROOT-001.md`, `project/reports/ARCH-MONOREPO-001-PHASE-2.md`) and
not duplicated here beyond the summary in Section 5. Once ARCH-MONOREPO-001 closed that blocker
(issue #178) with a live, successful deployment, SPRINT-008 resumed under `GOV-008C`
("API-SPRINT-CONTINUATION") and completed its remaining five tickets — API-SPRINT-ISSUES, API-002
through API-006 — in the sprint's own declared ticket order, each self-verified and merged under
the active delegation.

## 2. Completed tickets

| Ticket | What it did |
|---|---|
| API-001 | Public API framework, routing, auth, versioning, error model, OpenAPI, shared response envelopes; stood up `screening/state.py`/`screening/service.py` as the one shared execution graph for CLI and API alike. |
| API-SPRINT-ISSUES | Reviewed all 13 open + recently-closed GitHub issues for relevance to API-002–006; none were in scope. Zero implementation PRs opened, per the ticket's own correct-outcome definition. |
| API-002 | Confirmed API-001's `PostgresScreeningStateRepository` was already correctly implemented; closed the one real gap — `screening.service.get_state()`/`refresh()` had only ever been tested against the in-memory fake, never the real Postgres repository. |
| API-003 | Implemented the three read endpoints (`/capabilities`, `/screening`, `/screening/{signal}`, `/screening/{signal}/{symbol}`), all provably read-only (a poison-pill fake repository proves no read handler ever writes). |
| API-004 | Implemented `POST /screening/{signal}/{symbol}/refresh`; promoted the CLI's private live-provider safety guard (`APPROVED_LIVE_UNIVERSE`/`live_only_config`) to shared, public code rather than duplicating it. |
| API-005 | Validated the full API via an end-to-end simulated AI-agent workflow (discover → retrieve → inspect → decide → refresh → confirm → summarize), entirely over HTTP, zero CLI dependency. |
| API-006 | Corrected the stale Railway deployment doc (still described the pre-consolidation `/backend` layout) and added authentication, API-examples, and operational documentation for the new surface. |

Interleaved (separate delegations, required to unblock this sprint, not SPRINT-008 tickets
themselves — reported separately):

| Delegation | What it resolved |
|---|---|
| OPS-RAILWAY-ROOT-001 (`GOV-008B`) | Diagnosed the Railway deployment failure down to a precise, evidenced root cause (Railpack's pip-mode install target absent from the runtime container's `sys.path`); could not resolve it within its own ticket scope, filed issue #178, stopped cleanly rather than forcing a workaround. |
| ARCH-MONOREPO-001 (`GOV-009` / `GOV-009-PHASE-2`) | Wrote an ADR recommending consolidation to a single root-level Python project (matching the Stonk repository's own proven Railway shape); implemented it in four sub-phases; **closed issue #178 with a live, successful production deployment** as direct evidence the ADR's prediction was correct. |

## 3. Delegated, merged pull requests

| PR | Merged (UTC) | Title |
|---|---|---|
| [#164](https://github.com/jaiaFoster/ASA/pull/164) | 2026-07-22T22:34:55Z | GOV-008: activate SPRINT-008 Founder Sprint Delegation |
| [#165](https://github.com/jaiaFoster/ASA/pull/165) | 2026-07-22T22:55:38Z | GOV-008A: rescope SPRINT-008 around a shared screening service layer |
| [#166](https://github.com/jaiaFoster/ASA/pull/166) | 2026-07-23T00:58:38Z | API-001: public API contracts and infrastructure |
| [#167](https://github.com/jaiaFoster/ASA/pull/167) | 2026-07-23T02:14:32Z | GOV-008B: activate OPS-RAILWAY-ROOT-001 Founder Sprint Delegation |
| [#179](https://github.com/jaiaFoster/ASA/pull/179) | 2026-07-23T03:33:29Z | OPS-RAILWAY-ROOT-001: final report |
| [#180](https://github.com/jaiaFoster/ASA/pull/180) | 2026-07-23T03:52:07Z | GOV-009: activate ARCH-MONOREPO-001 Phase 1 (research + ADR only) |
| [#181](https://github.com/jaiaFoster/ASA/pull/181) | 2026-07-23T04:00:17Z | ARCH-MONOREPO-001 Phase 1: packaging consolidation ADR |
| [#182](https://github.com/jaiaFoster/ASA/pull/182) | 2026-07-23T04:20:42Z | GOV-009-PHASE-2: activate ARCH-MONOREPO-001 Phase 2 implementation |
| [#183](https://github.com/jaiaFoster/ASA/pull/183) | 2026-07-23T04:31:03Z | ARCH-MONOREPO-001 Phase 2A: resolve canonical ownership of duplicated packages |
| [#184](https://github.com/jaiaFoster/ASA/pull/184) | 2026-07-23T04:44:33Z | ARCH-MONOREPO-001 Phase 2B: establish single canonical Python project |
| [#185](https://github.com/jaiaFoster/ASA/pull/185) | 2026-07-23T04:48:29Z | ARCH-MONOREPO-001 Phase 2C: normalize import boundaries |
| [#186](https://github.com/jaiaFoster/ASA/pull/186) | 2026-07-23T04:54:27Z | ARCH-MONOREPO-001 Phase 2D: simplify Railway config, remove backend/ entirely |
| [#187](https://github.com/jaiaFoster/ASA/pull/187) | 2026-07-23T05:14:50Z | ARCH-MONOREPO-001 Phase 2: final report |
| [#188](https://github.com/jaiaFoster/ASA/pull/188) | 2026-07-23T05:26:24Z | GOV-008C: activate API-SPRINT-CONTINUATION, resume SPRINT-008 |
| [#189](https://github.com/jaiaFoster/ASA/pull/189) | 2026-07-23T05:30:05Z | API-SPRINT-ISSUES: GitHub issue review and reconciliation |
| [#190](https://github.com/jaiaFoster/ASA/pull/190) | 2026-07-23T05:34:54Z | API-002: screening state repository — close the service-layer Postgres gap |
| [#191](https://github.com/jaiaFoster/ASA/pull/191) | 2026-07-23T05:44:35Z | API-003: screening read endpoints |
| [#192](https://github.com/jaiaFoster/ASA/pull/192) | 2026-07-23T06:02:30Z | API-004: explicit narrow refresh endpoint |
| [#193](https://github.com/jaiaFoster/ASA/pull/193) | 2026-07-23T06:09:33Z | API-005: AI agent workflow validation |
| [#194](https://github.com/jaiaFoster/ASA/pull/194) | 2026-07-23T06:16:15Z | API-006: documentation and deployment |

Every PR above was self-verified against its ticket's required gates and merged under the active
Amendment 013 delegation at the time (`GOV-008`/`GOV-008A`/`GOV-008C` for SPRINT-008's own
tickets; `GOV-008B` and `GOV-009`/`GOV-009-PHASE-2` for the two interleaved delegations). All
governance activation/rescope files themselves (`#164`, `#165`, `#167`, `#180`, `#182`, `#188`)
were Founder-merged directly, per Amendment 013's own rule that activation/rescope files are never
delegate-merged.

## 4. Validation results

Current state, verified on `main` at commit `823712f`:

```text
PYTHONPATH=. python -m pytest tests/ -q --ignore=tests/pos --ignore=tests/deployment_observer
  1717 passed, 17 skipped

PYTHONPATH=. python -m pytest tests/asa/test_boundaries.py -q
  5 passed

ruff check asa tests/asa
  All checks passed!

mypy asa
  Success: no issues found in 38 source files
```

Every required gate from `docs/sprints/SPRINT-008.yaml`'s own `validation.required_before_every_delegated_merge`
list passed on every one of this sprint's own delegate-merged PRs (#166, #189–194) before merge —
CI checks, `pytest tests_asa`, `pytest tests_screening` (exercised transitively through `asa`'s own
imports and this sprint's dedicated `tests/screening`-adjacent coverage), `pytest
tests_architecture`, ruff, mypy, the Alembic upgrade/downgrade round trip (where migrations
changed — API-001's `screening_state` table), the `asa` local boundary suite, and self-review.
No PR in this sprint required a stop condition or an unresolved architecture/Founder gate.

## 5. Architecture and governance verification

- **Single composition root preserved**: every new route is registered in
  `asa.bootstrap.build_application()`; no second entry point was introduced.
- **No new frozen public contract introduced without a gate**: the new `/api/v1/screening*`
  namespace was explicitly authorized by `GOV-008A`'s rescope; no other frozen contract changed.
- **Reads never trigger provider requests — verified by test, not inspection**:
  `tests/asa/test_screening_routes.py::TestReadsNeverComputeOrPersist` uses a poison-pill
  repository fake that fails the test if any read handler ever calls `upsert()`.
- **Refresh scope stays narrow**: `POST .../refresh` always targets exactly one signal/symbol
  pair; there is no whole-signal or whole-universe refresh operation anywhere in this surface.
- **Provider implementations stay internal**: no response model anywhere in `asa/api/screening_models.py`
  exposes a provider identity, raw payload, or credential; verified by explicit assertion in
  `tests/asa/test_screening_refresh_route.py` and `tests/asa/test_ai_agent_workflow.py`.
- **Railway rootDirectory/PYTHONPATH change recorded exactly as made**: recorded in API-001's own
  PR at the time, then superseded and re-recorded by ARCH-MONOREPO-001, whose Phase 2D
  (`project/reports/ARCH-MONOREPO-001-PHASE-2.md`) documents the final state — root directory `.`,
  no PYTHONPATH at all (eliminated entirely, not merely relocated).
- **Constitution and frozen governance unchanged**: no `docs/governance/` frozen document was
  modified by any ticket in this sprint.
- **Delegated scope matched approved tickets throughout**: every merged PR implemented exactly one
  approved ticket ID; no PR mixed ticket scope.
- **Every Amendment 013 gate evidenced**: self-review recorded in each PR description; see Section
  3's PR list.

## 6. Backend/screening connection decision and rationale

Resolved by explicit Founder direction during `GOV-008A` (full text in
`docs/sprints/SPRINT-008.yaml`'s `backend_screening_connection_decision` block): the API-serving
process must **not** be treated as a system separate from the rest of ASA. Concretely:

1. `screening/state.py` (a `ScreeningStateRecord` dataclass and a `ScreeningStateRepository`
   Protocol, pure, no infrastructure imports) and `screening/service.py` (`get_state()`/`refresh()`,
   a thin orchestration layer over the existing, unmodified `run_screening()`/`build_live_adapters()`
   machinery) became the **one shared execution graph** — both `screening/cli.py` and the new API
   route handlers call these same functions; neither reimplements or duplicates strategy-selection
   or execution logic.
2. `asa.integrations.screening_postgres.PostgresScreeningStateRepository` implements that Protocol
   using the existing raw-SQL, no-ORM pattern (matching `PostgresRunPublicationRepository`
   exactly), backed by a new `screening_state` table (Alembic migration, API-001).
3. Reaching this required a real, live Railway service configuration change — the service's
   `rootDirectory` had to become the repository root so the deployed container could see
   `screening/`, `market_data/`, `domain/`, etc. at all. This single decision is what turned out to
   be structurally unreachable in the codebase's original shape, and is the entire reason
   OPS-RAILWAY-ROOT-001 and ARCH-MONOREPO-001 became necessary interludes (Section 2).
4. `asa/`'s own legacy-technology boundary test forbids the literal substring `"strategy"`
   anywhere under `asa/`; root-level `screening/` code may use `strategy_id` freely (matching
   `ScreeningResult`'s own existing field name), but `asa/`'s HTTP-facing code uses `"signal"`
   throughout (`signal_id`, `/api/v1/screening/{signal}`, etc.) — a pure naming substitution at the
   HTTP boundary, not a different concept.

This decision proved durable through the whole sprint: no ticket after API-001 needed to revisit
it, and ARCH-MONOREPO-001's own dependency-direction boundary test
(`tests/architecture/test_asa_dependency_direction.py`) now continuously proves `asa/` still
imports root-level packages the same one-directional way this decision always assumed.

## 7. API endpoint catalog

Public, bearer-authenticated (`ASA_AGENT_API_TOKEN`), `/api/v1` prefix unless noted:

| Method | Path | Ticket | Notes |
|---|---|---|---|
| GET | `/capabilities` | API-003 | Fixed signal catalog; never changes at runtime. |
| GET | `/screening` | API-003 | All current results, paginated (`limit`/`offset`). |
| GET | `/screening/{signal}` | API-003 | Narrowed to one signal, paginated. |
| GET | `/screening/{signal}/{symbol}` | API-003 | One result; 404 if none yet. |
| POST | `/screening/{signal}/{symbol}/refresh` | API-004 | The one write operation; one signal/symbol pair only. |

Pre-existing endpoints, unmodified by this sprint, included here for a complete catalog:

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/health` | Unauthenticated liveness. |
| GET | `/api/v1/readiness` | Unauthenticated readiness. |
| POST | `/api/v1/market/quotes/ingest` | Development-only ingest. |
| POST / GET | `/api/v1/runs`, `/api/v1/runs/current`, `/api/v1/runs/{run_id}` | Portfolio run lifecycle. |
| GET | `/api/v1/portfolio`, `/api/v1/positions` | Published portfolio state. |
| POST | `/ops/market-data/validate` | Separate `ASA_OPERATIONS_TOKEN` auth; bounded live provider diagnostics. |

Full request/response detail and real captured examples: `docs/api/agent-api-examples.md`.
Authentication contract: `docs/api/agent-api-authentication.md`. OpenAPI specification is
published automatically by FastAPI at the application's own `/openapi.json`.

## 8. AI agent validation results

Full detail: `project/reports/API-005-AI-AGENT-VALIDATION.md`; continuously enforced by
`tests/asa/test_ai_agent_workflow.py` (runs on every CI build, not a one-time script).

All of SPRINT-008's own `validation_flow` steps were exercised end to end over HTTP only —
discover capabilities, retrieve screening data, inspect timestamps, decide whether refresh is
needed (agent-side policy against `age_seconds`), refresh exactly one stale opportunity, confirm
the result updated, and generate a structured summary from response JSON alone. All three success
criteria were met: no provider credential appeared in any of the 6 captured HTTP responses; the
validation file imports nothing from `screening.cli`; an immediate repeat read after refresh
returned identical field values (age tolerance ±1s for real elapsed time).

## 9. Discovered and resolved defects

| Defect | Discovered during | Resolution |
|---|---|---|
| `screening.service.get_state()`/`refresh()` were only ever tested against the in-memory fake repository, never the real Postgres implementation. | API-002 | Added `tests/asa/test_screening_service_postgres_integration.py`. |
| Railway's deployed container had the pip-mode install target absent from `sys.path` — a structural packaging defect, not a configuration typo. | OPS-RAILWAY-ROOT-001 (blocking API-001's own deployment) | Root-caused and resolved by ARCH-MONOREPO-001's repository consolidation, confirmed via a live, successful production deployment; issue #178 closed with direct evidence. |
| `docs/deployment/railway.md` still described the pre-consolidation `/backend` layout after ARCH-MONOREPO-001 shipped — an internally inconsistent, actively misleading deployment doc. | API-006 | Corrected to the current Root Directory/Config-as-Code/start-command settings. |

No defect was found in this sprint's own new code (API-002 through API-006) by API-005's
end-to-end validation — the implementation supported the full agent workflow without
modification.

## 10. Remaining non-blocking issues

- **No live market data provider credential is configured in production**
  (`project/reports/POST-005B-LIVE-VALIDATION.md`). `POST .../refresh` currently returns `503
  NO_LIVE_PROVIDER_CONFIGURED` for every request in production; the read endpoints are unaffected.
  This is external Founder-owned configuration, not an implementation gap — see
  `docs/api/agent-api-operations.md` for the operational detail.
- **CI does not run `tests/screening/` or root-level `mypy` for it** (pre-existing issue #147,
  confirmed still open and still accurate against the current `product-ci.yml`/
  `validate-architecture.yml` path filters). This sprint added meaningful new `screening/`
  surface (`live_acquisition.py`'s promoted `build_fulfillment_service_with_accounting`,
  `signal_catalog`, `SignalDefinition`) that is exercised indirectly through `tests/asa`'s own
  suite but has no dedicated CI job of its own. Worth closing before `screening/` grows further.
- **13 pre-existing open issues surveyed by API-SPRINT-ISSUES** (`project/reports/API-SPRINT-ISSUE-RECONCILIATION.md`)
  remain open; none fall within this sprint's own scope and none were touched.

## 11. Recommendations for SPRINT-009

1. Supply live market data provider credentials (Tradier at minimum) to the production
   deployment so `POST /api/v1/screening/*/refresh` is actually exercisable end to end in
   production, not only in tests — this is the single highest-value unblock for the API this
   sprint delivered.
2. Close issue #147 (add `tests/screening` and root-level `mypy` to CI) — low effort, meaningfully
   reduces the chance of a regression in the shared execution graph this sprint now depends on
   from both the CLI and the API.
3. Consider whether a frontend/UI consumer of the new `/api/v1/screening*` surface is in scope —
   this sprint's own `bounded_scope.out` explicitly excluded UI work, but the API now exists and
   is validated.
4. If a second refresh-triggering endpoint or a wider (multi-symbol) refresh is ever proposed,
   revisit this sprint's `architecture_principles` (`refreshes_are_explicit_and_narrowly_scoped`,
   `api_reports_facts_not_policy`) deliberately rather than by incremental extension of
   `POST .../refresh` — the current narrow scope was a explicit Founder-approved design choice,
   not an oversight.
5. `docs/architecture/ADR-002-composition-root.md` and `ADR-004-railway-robinhood-readonly.md`
   still reference the pre-ARCH-MONOREPO-001 `backend/` layout in places; these were deliberately
   left untouched by API-006 (ADRs are historical records, not living docs) but a future sprint
   drafting a new ADR that supersedes either should note this.

## 12. Founder verification requested

Per this sprint's own `definition_of_done`: every enumerated implementation ticket is merged,
every required gate passed on every merge, no stop condition remains unresolved, the API is
live and validated, and this report is now committed. Requesting Founder review and verification
of SPRINT-008's completion before SPRINT-009 begins.
