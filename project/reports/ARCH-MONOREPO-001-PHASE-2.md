# ARCH-MONOREPO-001 Phase 2 — Packaging Consolidation Implementation

Status: **Complete**. Implements Phase 1's ADR
(`architecture/ASA-ARCH-MONOREPO-001-Packaging-Consolidation-ADR.md`) end to end,
including live deployment validation. Founder verification requested per this
ticket's own `docs/sprints/ARCH-MONOREPO-001.yaml` (`phase_2_activation`,
GOV-AMD-001-013 / GOV-009-PHASE-2, #182).

Implementation window (UTC): 2026-07-23
Repository commit (final, `main`): `e2017b6`
Live deployment evidence: `9501d6a9-238e-4d3b-bfa9-f6856e9668b1` (commit `e2017b6`, `SUCCESS`)

## 1. Summary per sub-ticket

**2A — Canonical ownership** (PR #183): resolved every duplicated/vendored package
the ADR's own inventory identified, before touching the project's packaging
structure at all. Removed `backend/src/market_data/` and `backend/src/domain/`
(byte-identical vendored copies, kept in sync only by a now-deleted guard test);
consolidated two independently-drifting HTTP transport implementations
(`market_data/live_transport.py` vs `backend/src/asa/market_data_ops/transport.py`
— already diverged in naming, with nothing checking they stayed equivalent) into
one canonical copy; renamed `backend/src/asa/domain/` to `asa/contracts/`,
resolving a naming collision against root `domain/` the ADR flagged. Added
`tests/market_data/test_live_transport.py`, closing a real pre-existing gap:
neither prior copy had a dedicated unit test of its own HTTP-translation
behavior.

**2B — Packaging** (PR #184): moved `backend/src/asa/` to a repository-root
`asa/` package, alongside `screening/`, `market_data/`, `strategies/`,
`analytics/`, `domain/` — the ADR's recommended single-root-project
consolidation (Option 3), matching Stonk's (ASA's own migration predecessor)
proven Railway deployment shape. Moved `alembic.ini`, `migrations/`, `tests/`
(nested under the existing root `tests/` package as `tests/asa/`),
`.python-version`, `requirements.txt`. Replaced `backend/pyproject.toml` with
one root-level `pyproject.toml` — the old `mypy_path`/`pythonpath` `"src:.."`
split is gone entirely, since `asa/` and everything it imports are now plain
siblings at the repository root. Fixed every stale path reference the move
required (test path arithmetic, `tests.fakes` → `tests.asa.fakes` imports).
`backend/railway.json`'s commands could no longer stay `cd backend && ...` —
`alembic.ini`/`asa/` no longer lived there at all, so the old form was
structurally broken as of this same commit, not merely suboptimal — updated to
run directly from the repository root.

**2C — Imports** (PR #185): PYTHONPATH elimination was already a complete side
effect of Phase 2B's moves, confirmed via an explicit repo-wide audit (no
remaining PYTHONPATH usage or `sys.path` manipulation anywhere in `asa/`'s own
dependency graph). The remaining "normalize package boundaries" work: added
`tests/architecture/test_asa_dependency_direction.py`, formalizing the
one-directional relationship the whole consolidation depends on (`asa/` imports
root packages; nothing imports back from `asa/`) with the same AST-scanning
approach already established for ADR-004's own pipeline-layer ordering, plus
guard-the-guard checks confirming both halves of the relationship still hold.

**2D — Deployment** (PR #186 + live validation): moved `railway.json` (the last
file remaining under `backend/`) to the repository root and removed the
now-fully-empty `backend/` directory entirely. Fixed stale docstrings discovered
during a final repo-wide sweep that asserted something now false rather than
merely historical (`screening/live_acquisition.py` claimed it "cannot import
backend/," which no longer exists in any sense). Fixed `compose.yaml`'s local
Docker Compose dev environment (`working_dir: /app/backend` no longer existed).
After the Founder updated Railway's "Config as Code" file path dashboard
setting to `/railway.json`, triggered and confirmed a fully successful live
deployment — see Section 5.

## 2. Files moved or removed

Aggregate across all four sub-tickets (`cd50c43`..`e2017b6`, the full Phase 2
implementation window): **118 files changed, 356 insertions(+), 8413
deletions(-)** — a net reduction of **8,057 lines**. 39 files deleted outright
(vendored copies, the retired transport duplicate, the old
`backend/pyproject.toml`, the retired `test_vendor_sync.py` guard); the
remainder renamed via `git mv` with history preserved (confirmed: every rename
shows as a `R`, not a `D`+`A` pair, in `git log --follow`).

- **Removed entirely:** `backend/` (the directory itself, including its own
  `.venv`/`.mypy_cache`/`.pytest_cache`/`.ruff_cache`, all local/gitignored),
  `backend/src/market_data/` (18 files), `backend/src/domain/` (18 files),
  `backend/src/asa/market_data_ops/transport.py`,
  `backend/tests/market_data_ops/test_vendor_sync.py`, `backend/pyproject.toml`.
- **Moved (git mv, history preserved):** `backend/src/asa/` → `asa/`;
  `backend/src/asa/domain/` → `asa/contracts/`; `backend/alembic.ini` →
  `alembic.ini`; `backend/migrations/` → `migrations/`; `backend/tests/` →
  `tests/asa/`; `backend/.python-version` → `.python-version`;
  `backend/requirements.txt` → `requirements.txt`; `backend/railway.json` →
  `railway.json`.
- **Added:** one root-level `pyproject.toml` (replacing
  `backend/pyproject.toml`); `tests/market_data/test_live_transport.py`;
  `tests/architecture/test_asa_dependency_direction.py`.

## 3. Before/after token-efficiency analysis

Per this ticket's own `phase_2_success_metrics.token_efficiency` requirement.

**Files touched for a representative common feature change** — extending a
shared type both the CLI and the API consume (e.g. a new field on a Market
Data value type):
- **Before:** the root-level `domain/` or `market_data/` file, *plus* its
  byte-identical vendored copy under `backend/src/` (kept in sync only by a
  dedicated guard test — a synchronization step that itself needed to be
  understood and maintained), *plus* awareness of `backend/pyproject.toml`'s
  `mypy_path = "src:.."` to know why the change would or wouldn't be visible
  to backend's own mypy run.
- **After:** the root-level file only. `asa/` imports it directly, the same
  way `screening/` always has. No vendored copy, no sync guard, no
  `mypy_path` to reason about.

**Duplicated modules removed:** 36 vendored files (`backend/src/market_data/`
+ `backend/src/domain/`) plus one independently-drifting duplicate
(`backend/src/asa/market_data_ops/transport.py`) — 37 files whose entire
purpose was staying identical to code that already existed elsewhere.

**Duplicated configs removed:** two `pyproject.toml` files (root-level
`asa`-adjacent config had never existed as such; `backend/pyproject.toml`
existed *instead of* a root one) collapsed to one; two Python-version/
dependency-manifest surfaces (`backend/.python-version` +
`backend/requirements.txt`, separate from anything at the repository root)
collapsed to one each; the `test_vendor_sync.py` guard test (49 lines whose
only job was catching drift between the two copies removed above) is gone
because there is nothing left to drift.

**Import complexity reduced:** `mypy_path = "src:.."` and
`pythonpath = ["src", ".."]` (both required specifically because `asa/` lived
under a `src/` prefix inside a separate directory tree) are gone entirely —
confirmed via repo-wide grep, zero remaining PYTHONPATH usage or `sys.path`
manipulation anywhere in `asa/`'s own dependency graph. A new, automated
boundary test (`tests/architecture/test_asa_dependency_direction.py`) now
protects the one-directional import relationship that makes this
simplification safe, closing a gap that previously existed only by
convention.

**Deployment complexity reduced:** `railway.json`'s commands went from `cd
backend && export PYTHONPATH=src:.. && python -m alembic upgrade head && exec
python -m uvicorn asa.asgi:create_application --factory --host 0.0.0.0 --port
"${PORT}"` to `python -m alembic upgrade head && exec python -m uvicorn
asa.asgi:create_application --factory --host 0.0.0.0 --port "${PORT}"` — no
`cd`, no `PYTHONPATH` export, no custom Railpack install step (retired
earlier, in OPS-RAILWAY-ROOT-001, once its own root cause was understood).
`railpack.json` needed no changes at all in this ticket. The live deployment
this produced (Section 5) is the first one in this repository's history to
succeed from a repository-root `rootDirectory` — every prior attempt, across
OPS-RAILWAY-ROOT-001's own extensive investigation, failed at one stage or
another of exactly the complexity this consolidation removed.

## 4. Regression results

- **Full test suite** (excluding `tools/pos` and `tools/deployment_observer`,
  both deliberately separate per the ADR and confirmed independently
  unaffected: `tools/deployment_observer`'s own 70 tests pass via its own
  environment, untouched by this ticket): **1689 passed, 14 skipped**
  (Postgres-marked, no local Docker) as of the final commit.
- `tests/asa/` specifically: 83 passed throughout Phase 2A/2B (test count
  dropped by 2 in Phase 2A — the retired vendor-sync guard — then held
  steady).
- New tests added this phase: 6 (`test_live_transport.py`) + 20
  (`test_asa_dependency_direction.py`) = 26, all passing.
- `ruff check` and `mypy` clean throughout every sub-ticket (36 `asa/` source
  files, unchanged count from before the move — confirming the move itself
  introduced no new files needing type coverage, only relocated existing
  ones).
- CI (`product-ci.yml`'s `backend` job, `validate-architecture.yml`): green on
  every PR that triggered them; PRs touching only doc/report files
  (deliberately) did not trigger path-filtered workflows, verified locally in
  those cases, matching this repository's established practice.

## 5. Railway deployment evidence

Deployment `9501d6a9-238e-4d3b-bfa9-f6856e9668b1`, triggered automatically by
the Phase 2D merge to `main` (commit `e2017b6`) once the Founder updated
Railway's "Config as Code" file path dashboard setting from
`/backend/railway.json` to `/railway.json` (a setting with no documented API
field, confirmed dashboard-only in OPS-RAILWAY-ROOT-001 — this ticket could
not have completed live validation without that Founder-side action).

- `rootDirectory: "."`, `configFile: "/railway.json"`,
  `pythonPackageManager: "pip"` (all confirmed via `getDeploymentInfoTool`).
- Every deployment stage completed: `SNAPSHOT_CODE`, `BUILD_IMAGE`,
  `PUBLISH_IMAGE`, `PRE_DEPLOY_COMMAND`, `CREATE_CONTAINER`, `HEALTHCHECK`,
  `CONFIGURE_NETWORK`, `DRAIN_INSTANCES` — the full lifecycle, including
  cutover (the new deployment now serves production traffic; the previous
  deployment was drained).
- Deploy logs confirm a real `python -m alembic upgrade head` ran
  successfully (`INFO [alembic.runtime.migration] Context impl
  PostgresqlImpl.` / `Will assume transactional DDL.`) — the exact command
  that failed with `No module named alembic` on every attempt throughout
  OPS-RAILWAY-ROOT-001 now succeeds, with no PATH tricks, no diagnostic
  workarounds, nothing beyond the plain command.
- Uvicorn started cleanly (`INFO: Application startup complete.` /
  `INFO: Uvicorn running on http://0.0.0.0:8080`), and real health-check
  requests returned `200 OK`.
- Independently confirmed via direct `curl`: `GET /api/v1/health` →
  `200 {"status": "ok"}`.
- Issue [#178](https://github.com/jaiaFoster/ASA/issues/178) (Railpack's
  pip-mode install target not on the runtime `sys.path`, OPS-RAILWAY-ROOT-001's
  own unresolved blocker) is **closed** with this evidence — the ADR's
  prediction (that this was a structural consequence of the split-root
  packaging shape, not an isolated Railpack quirk) is confirmed correct: the
  consolidation resolved it as a side effect of removing its precondition,
  not through any Railpack-specific workaround.

## 6. Explicit success-metric verification

Per `docs/sprints/ARCH-MONOREPO-001.yaml`'s `phase_2_success_metrics`:

- **Architecture:** one runtime dependency graph (one `pyproject.toml`); one
  canonical package owner per module (Section 2/3); no duplicated runtime
  implementations (Section 3) — all confirmed.
- **Deployment:** no PYTHONPATH manipulation (confirmed via repo-wide audit,
  Phase 2C); no repository-root ambiguity (`backend/` no longer exists);
  standard Railway deployment (Section 5) — all confirmed.
- **Maintenance:** fewer synchronized edits (no vendored copies left to keep
  in sync); fewer deployment-specific files (`railway.json`'s own commands
  simplified); simpler onboarding (one project root, one obvious entrypoint,
  matching Stonk's own proven shape) — all confirmed.

## 7. Remaining limitations and open questions

Carried forward from the ADR's own "Open Questions" (Phase 1), still
genuinely open (not resolved by Phase 2, and not blocking):

- Whether `docs/architecture/` (backend-specific ADR series) and
  `architecture/` (root-level ADR series) should also consolidate — noted in
  the ADR as out of scope, unchanged by this ticket.
- `tests/asa/` remains a distinct subdirectory of the unified `tests/`
  package rather than merging individual files into the root suites they're
  adjacent to (e.g. `tests/asa/market_data_ops/` vs `tests/market_data/`) —
  a deliberate, minimal-disruption choice (Phase 1's ADR left this decision
  to Phase 2's own implementation), not a defect.
- `product-ci.yml`'s `backend` job (name unchanged for minimal disruption)
  still runs `ruff`/`mypy`/`pytest` scoped narrowly to `asa`/`tests/asa`,
  not the full repository — deliberately, to avoid expanding CI enforcement
  scope as a side effect of a packaging move (issue #147, CI coverage gaps
  for root-level packages, remains separately tracked and unaffected).

No new issues were opened by this ticket beyond closing #178.

## 8. Confirmation: no secrets exposed

No credential values were read, printed, exported, or committed at any point
in this ticket's work. The one live infrastructure action beyond repository
commits — confirming the Railway service's `rootDirectory`/`configFile`
settings and reading deployment status/logs — used only read-only Railway
MCP tool calls; the Founder's own dashboard update (the "Config as Code"
file path) was performed by the Founder directly, its value never seen by
the implementing agent.

## 9. Deliverables

- `project/reports/ARCH-MONOREPO-001-PHASE-2.md` — this report.
- `asa/`, `alembic.ini`, `migrations/`, `tests/asa/`, `pyproject.toml`,
  `railway.json`, `.python-version`, `requirements.txt` — the consolidated
  repository-root project (moved from `backend/`, which no longer exists).
- `tests/market_data/test_live_transport.py`,
  `tests/architecture/test_asa_dependency_direction.py` — new regression
  and boundary coverage.
- `docs/sprints/ARCH-MONOREPO-001.yaml` — the Founder Sprint Delegation
  record for both phases (GOV-009 / GOV-009-PHASE-2, #180 / #182).
- Issue [#178](https://github.com/jaiaFoster/ASA/issues/178) — closed, with
  live deployment evidence.
