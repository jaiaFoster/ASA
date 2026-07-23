<!-- Repository path: architecture/ASA-ARCH-MONOREPO-001-Packaging-Consolidation-ADR.md -->

# ASA-ARCH-MONOREPO-001: Repository Packaging Consolidation

**Status:** Accepted — Founder-approved via the "GOV-009-PHASE-2: Packaging Consolidation
Implementation" handoff. Phase 2 (implementation) is now activated; see
`docs/sprints/ARCH-MONOREPO-001.yaml`'s `phase_2_activation` block.
**Date:** 2026-07-23
**Delegation:** GOV-AMD-001-013 / GOV-009 (#180), `docs/sprints/ARCH-MONOREPO-001.yaml`
**Scope:** This document is Phase 1's own deliverable — research and recommendation only. It
was intentionally free of implementation changes at the time it was written. Phase 2
implementation work is tracked separately, under its own activation, not by editing this
document.

## Context

### Why did the existing layout evolve?

`backend/` was established from its first commit (`4390331`, ASA-PROD-001, "establish market
observation slice") as a fully self-contained, independently deployable service: its own
`pyproject.toml` (hatchling build backend, `packages = ["src/asa"]`), its own dependency list,
its own test suite, deployed to Railway with `rootDirectory: /backend` — a clean "isolated
monorepo" pattern (Railway's own term; see Research below) where the deployed subtree needed
nothing outside itself.

That isolation held until PR #136 ("Add protected bounded live Market Data validation
endpoint on Railway"), which needed `backend/` to reuse the root-level `market_data/` and
`domain/` packages' validation logic for a live-provider-validation endpoint. Rather than
widen the deployment root, that PR **vendored** — byte-copied — both packages into
`backend/src/market_data/` and `backend/src/domain/`, guarded by
`backend/tests/market_data_ops/test_vendor_sync.py`, which fails if the two copies drift.
This kept `backend/` deployable from its own subtree while reusing two small, comparatively
stable packages.

SPRINT-008 (API-001, GOV-008A) broke that pattern's assumptions. The Founder's own explicit
direction for that sprint was: *"Don't treat the API backend as a separate system from ASA...
Both the CLI and the HTTP API should call the same service methods, so there is a single
execution graph and a single source of truth."* This ruled out vendoring a third copy of
`screening/`'s logic — `screening/service.py`'s `get_state()`/`refresh()` is the literal
execution graph the Founder required to be shared, not duplicated, and it transitively pulls
in `market_data/`, `strategies/`, `analytics/`, `domain/`, `screening/registry.py`,
`screening/runner.py`, and more. Vendoring a byte-identical copy of that surface would be
both a direct violation of the stated principle and an ever-growing maintenance burden as
`screening/`'s surface keeps changing (unlike `market_data/`/`domain/`, which are comparatively
stable value/protocol definitions).

The chosen alternative — the one still in place today — was to widen Railway's
`rootDirectory` from `/backend` to the repository root and extend `PYTHONPATH` (`src:..`) so
`backend/`'s process can import root-level packages directly. **This is the origin of the
current problem.** OPS-RAILWAY-ROOT-001 (`project/reports/OPS-RAILWAY-ROOT-001.md`) then spent
an entire investigation discovering how many ways that widening interacts badly with
Railpack's own undocumented, Python-monorepo-unaware build behavior — a broken custom install
step, an unsupported command-parser syntax, a root-level `uv.lock` that made Railpack install
the wrong project's dependencies, and a still-unresolved issue (#178) where Railpack's
pip-mode install target isn't on the runtime container's `sys.path` at all. None of these are
bugs in ASA's business logic; all of them are consequences of asking a single-package-detection
tool (Railpack) to build a shape it was never designed to build.

### Why did Railway deployment originally work?

Because `rootDirectory: /backend` gave Railpack exactly the shape it is built for: one
directory, one `pyproject.toml`, one dependency file, one detected Python app. Railway's own
documentation (see Research) explicitly distinguishes "isolated" monorepos (root-directory-
scoped, works today for any language) from "shared" monorepos (root-level shared code, only
first-class-supported for JavaScript package managers — pnpm/npm/yarn/bun — with no equivalent
documented mechanism for Python). ASA's current layout is, by Railway's own taxonomy, a
Python "shared" monorepo — the one shape Railway does not claim to support well.

### What architectural change required widening deployment scope?

SPRINT-008/API-001's shared execution-graph requirement (above) — specifically, the decision
that `backend/` must call `screening/service.py` directly rather than reimplement or vendor
its logic.

### Every runtime package boundary

Root-level (18 packages, one `__init__.py`-bearing directory per pipeline layer, governed by
`architecture/ADR-004-repository-organization.md`'s strict one-way dependency rule
`providers → observation → reconciliation → facts → indicators → strategies → guardrails →
ranking → presentation`, plus the operational-analysis packages `position_proposals/`,
`portfolio/`, `risk/`, `execution_planning/`, `simulation/`, and the shared `domain/` module):

`analytics/`, `domain/`, `execution_planning/`, `facts/`, `guardrails/`, `indicators/`,
`market_data/`, `observation/`, `portfolio/`, `position_proposals/`, `presentation/`,
`providers/`, `ranking/`, `reconciliation/`, `risk/`, `screening/`, `simulation/`,
`strategies/`.

None of these declare a `pyproject.toml` of their own, and none has a third-party dependency
beyond the Python standard library — confirmed by grepping every top-level import in
`screening/`, `analytics/`, `strategies/`, `market_data/`, `domain/` for non-stdlib,
non-internal names: none exist. This is a direct, deliberate consequence of the "zero
infrastructure imports" architecture principle already established for `screening/` (and, by
`ADR-004`'s narrower dependency rules, for `indicators/`, `strategies/`, and `guardrails/`
too). **These packages need to be importable, not independently dependency-managed.**

`backend/` (one deployable service, `hatchling`-built, `packages = ["src/asa"]`):
`backend/src/asa/` — API routes, application use cases, bootstrap/composition root
(`docs/architecture/ADR-002-composition-root.md`), infrastructure integrations
(`asa.integrations`), and `asa.market_data_ops` (the live-validation endpoint from PR #136).
Has a real, substantial third-party dependency list: `alembic`, `fastapi`, `psycopg[binary]`,
`pydantic-settings`, `robin-stocks`, `sqlalchemy`, `uvicorn`.

`tools/deployment_observer/` (one small, unrelated dev-tooling script pair, relocated here
from the repository root by OPS-RAILWAY-ROOT-001 — its own `pyproject.toml`/`uv.lock`,
`dependencies=[]`, `mypy`/`pytest`/`pyyaml`/`ruff` as its only, dev-only, dependencies).

**Dependency direction is strictly one-way**, confirmed by grep: `backend/src/asa/` imports
`screening.state` (today) and is architecturally committed to importing more of
`screening/service.py`'s surface as API-003/API-004 land; no root-level package imports
anything from `backend/`. This one-directional graph is what makes every option below
tractable — there is no cycle to break.

### Duplicated / vendored packages

1. **`backend/src/market_data/` and `backend/src/domain/`** — verbatim vendored copies of
   root `market_data/` and `domain/`, kept identical by `test_vendor_sync.py`. Confirmed
   byte-identical (apart from `__pycache__`) as of this ADR.
2. **`market_data/live_transport.py` vs `backend/src/asa/market_data_ops/transport.py`** — an
   *independent, hand-maintained, non-identical* second implementation of the same HTTP
   transport adapter, one for root-level callers (`screening/`'s `--live` CLI path), one for
   `backend/`. Its own docstring explains why: `screening/`'s architecture boundary forbids it
   from importing `urllib` or performing network I/O directly, and `backend/` cannot import
   root-level `market_data/` at all under the pre-SPRINT-008 model. **Unlike the vendored
   pair above, nothing enforces these two stay behaviorally equivalent** — a real, currently
   unguarded drift risk, discovered during this ADR's own research (function names already
   differ: `build_live_transport` vs `build_transport_for_provider`).
3. **A naming collision, not duplication:** `backend/src/asa/domain/` (API/service-layer
   response-shaping types — `CacheStatus`, `FreshnessStatus`, etc.) and root-level `domain/`
   (cross-cutting Market Data/financial value types) are two *unrelated* packages that happen
   to share the name `domain`. This is a source of real confusion for anyone reading an
   import statement out of context and should be resolved by whichever option is chosen below
   (e.g., renaming `asa.domain` to something like `asa.contracts`), even though it is not
   itself duplicated code.

### Why the repository currently requires PYTHONPATH

`backend/src/asa/bootstrap.py` and `backend/src/asa/integrations/screening_postgres.py`
import `screening.state` directly (not the vendored-copy pattern used for `market_data`/
`domain`). For that import to resolve, the Python process's import path must include both
`backend/src` (for `asa`'s own internal imports, unchanged since ASA-PROD-001) and the
repository root (for `screening` and, transitively once API-003/004 land, `market_data`,
`strategies`, `analytics`, `domain`). `backend/pyproject.toml`'s `pythonpath = ["src", ".."]`
(pytest) and `mypy_path = "src:.."` (mypy) encode this locally; `backend/railway.json`'s
`export PYTHONPATH=src:..` encodes it for the deployed process. This is not accidental
misconfiguration — it is the direct, necessary consequence of one Python process needing to
resolve imports from two disjoint directory trees that share no common installable root.

## Research

**Stonk** (`/Users/jaiafoster/Claude/stonk`, ASA's own migration predecessor — see
`docs/migration/stonk-*.md`): no `pyproject.toml` at all. A plain `requirements.txt`, one flat
`app/` package containing the entire application (`api/`, `auth.py`, `config.py`, `db/`,
`models/`, `providers/`, `services/`, `strategies/`, `utils/`), thin root-level compatibility
re-export shims (e.g. `main.py` imports from `app.main`), and `railway.toml` with
`startCommand = "sh start.sh"` execing `gunicorn main:app` directly from the repository root.
Zero `PYTHONPATH` manipulation anywhere, because there is exactly one package tree and the
process starts where that tree's own entrypoint file already lives.

**Standard Python packaging**: a project is either (a) one installable package with one
`pyproject.toml` at its root, or (b) an explicit multi-package **workspace** — a first-class
concept in `uv` (`tool.uv.workspace.members`, one shared lockfile, `tool.uv.sources` with
`workspace = true` for inter-member dependencies, `uv run --package <name>` to run a specific
member as the entrypoint while still importing sibling members) and in Hatch (context-variable
path references between sibling projects, e.g. `{root:parent:parent:uri}`, less turnkey than
uv's). ASA's current layout is neither — it has no single installable root, and no
`pyproject.toml`-based workspace declaration; it approximates a workspace's *effect*
(cross-package imports) using raw `PYTHONPATH`, without any of a workspace's tooling support
(dependency resolution, lockfile, editable-install wiring, IDE/type-checker recognition).

**Railway deployment recommendations**: Railway's own documentation distinguishes "isolated"
monorepos (root-directory-scoped per service — well-supported, any language) from "shared"
monorepos (root-level shared code, custom start commands) — and explicitly limits first-class
shared-monorepo tooling and auto-detection to JavaScript package managers (pnpm, npm, yarn,
bun). No first-class, documented Python equivalent exists. This is not a gap this
investigation failed to find — it is a gap Railway's own documentation acknowledges. OPS-
RAILWAY-ROOT-001's entire investigation is a direct, concrete demonstration of the cost of
running a Python "shared monorepo" against a builder (Railpack) whose Python provider was not
designed for that shape: a broken custom install step, a start-command parser rejecting
ordinary shell conditionals, a root-level lockfile silently redirecting the wrong package
manager, and a still-open issue (#178) where the build succeeds but the runtime image cannot
see what pip installed.

## Decision

**Recommend Option 3: consolidate to a single root Python project**, matching Stonk's proven
model, eliminating `backend/`'s separate `pyproject.toml` and the vendored copies it currently
requires, and giving Railpack the one shape its Python provider is actually built for.

### Alternatives considered

**Option 1 — Extend vendoring to cover `screening/service.py`'s full surface.**
Continue the PR #136 pattern: byte-copy whatever of `screening/`, `market_data/`,
`strategies/`, `analytics/`, `domain/` that `backend/` needs into `backend/src/`, keep
`rootDirectory: /backend`, drop the `PYTHONPATH` extension entirely.
*Rejected.* Directly contradicts the Founder's explicit GOV-008A direction ("single execution
graph and a single source of truth," not a parallel copy). `screening/service.py`'s surface is
large and actively growing (API-003/API-004 are not yet implemented and will pull in more of
it), unlike the small, stable `market_data`/`domain` pair PR #136 vendored — the sync-guard
maintenance burden would only grow. This ADR's own research already found one *unguarded*
duplication (`market_data/live_transport.py` vs `backend/src/asa/market_data_ops/transport.py`)
that has already drifted in naming; extending vendoring is extending the exact failure mode
this ADR exists to eliminate, not fixing it.

**Option 2 — A `uv` workspace.** Declare a root `pyproject.toml` with
`tool.uv.workspace.members` covering the root-level packages and `backend/` as a member,
`tool.uv.sources` wiring `backend/`'s dependency on the shared code via `workspace = true`, one
shared lockfile, `uv run --package asa-backend` (or equivalent) as the Railway start command.
*Rejected as the primary recommendation, though the most "textbook-correct" packaging fix in
the abstract.* Two concrete problems specific to ASA's situation: (a) the root-level packages
this workspace would need as members have **zero third-party dependencies to resolve or
lock** — a workspace's central benefit (unified, conflict-checked dependency resolution across
packages with real third-party requirements) does not apply here, so its added complexity buys
little; (b) it still requires Railway's `rootDirectory` to be the repository root and Railpack
to correctly detect and build a `uv`-workspace-shaped Python project end-to-end — exactly the
category of undocumented, Railpack-version-sensitive behavior that produced OPS-RAILWAY-ROOT-001's
still-unresolved #178. A workspace does not remove the "ask Railpack to understand a
multi-package Python repo" risk; it only makes the multi-package declaration more formal.
Worth revisiting later if a genuine third-party-dependency-per-package need emerges that a flat
project can no longer express cleanly.

**Option 3 — Single root Python project (recommended).** Move `backend/src/asa/` to the
repository root (e.g. `asa/`), keeping its own internal package structure (`asa.api`,
`asa.application`, `asa.integrations`, `asa.market_data_ops`, etc.) and imports unchanged;
delete the vendored `backend/src/market_data/`/`backend/src/domain/` copies entirely, since
`asa/` would import root-level `market_data`/`domain` directly, the same way `screening/`
already does; delete `backend/`'s own `pyproject.toml`, folding its dependency list
(`alembic`, `fastapi`, `psycopg[binary]`, `pydantic-settings`, `robin-stocks`, `sqlalchemy`,
`uvicorn`) into one repository-root `pyproject.toml`/`requirements.txt`; Railway's
`rootDirectory` stays `.` but `railway.json`'s commands simplify to plain, unprefixed
`python -m alembic upgrade head`/`uvicorn asa.asgi:create_application`, with no `cd backend`
and no `PYTHONPATH` export at all, because everything is now one tree rooted where the
process already starts.
*Selected.* Directly matches Stonk's own proven, already-working Railway deployment shape.
Gives Railpack exactly the single-package-detection case it is built and documented for,
eliminating the entire class of problem OPS-RAILWAY-ROOT-001 spent its investigation on — not
mitigating it, removing its precondition. Most literal reading of GOV-008A's "single execution
graph, single source of truth": one project, one dependency graph, one package root, not
multiple formally-separate packages resolved together. Resolves the `asa.domain`/root
`domain` naming collision naturally as part of the same move (rename `asa.domain` to
`asa.contracts` or similar while relocating).

**Option 4 (considered, not selected) — Installable internal package via a local editable
path dependency, no formal workspace.** Give the root-level packages a single new
`pyproject.toml` (e.g. as `asa-core`), have `backend/`'s own `pyproject.toml` depend on it via
a local path reference, without `uv`'s or Hatch's formal workspace machinery.
*Rejected.* Still requires `rootDirectory` to be the repository root for the path dependency
to resolve at build time (the sibling directory must be in Railpack's build context), so it
inherits Option 2's core Railpack risk without even the benefit of a single shared lockfile.
A strictly worse version of Option 2 for this repository's specific needs.

## Consequences

- **Migration cost** (mechanical, not a business-logic rewrite, consistent with this ticket's
  own non-goals): move `backend/src/asa/` to a repository-root `asa/` package (a directory
  move plus updating any `backend/`-relative path assumptions, e.g. `alembic.ini`'s script
  location); delete `backend/src/market_data/`, `backend/src/domain/` (no longer needed once
  `asa/` imports root packages directly, the same way `screening/` already does); delete
  `backend/pyproject.toml`, replacing it with one root-level `pyproject.toml`; move
  `backend/tests/` to align with `asa/`'s new location (or merge into root `tests/`, a
  decision left to Phase 2's implementation plan); update `product-ci.yml`'s `backend` CI job
  to the new paths; rename `asa.domain` to resolve the naming collision noted above; delete
  `test_vendor_sync.py` (nothing left to vendor); update `backend/railway.json` (or its
  root-level equivalent) to the simplified, unprefixed commands.
- **Deployment impact**: `railway.json`'s commands become the plain form Railway's own parser
  and Railpack's own detection are best-tested against — no `cd`, no `PYTHONPATH` export, no
  custom install step, no workspace-awareness required of Railpack at all. This directly
  targets and should resolve issue #178 (Railpack's pip-mode install target not on the runtime
  `sys.path`) as a side effect, since that issue is specific to the current split-root shape;
  it cannot be confirmed resolved without Phase 2 implementation and a real deployment attempt.
- **Rollback strategy**: this is a repository-structure change with no database migration and
  no behavior change to the execution graph, domain model, or API/CLI contracts — a `git
  revert` of the consolidation commit(s) restores the exact prior structure. The live Railway
  service's `rootDirectory` and `railway.json` config would need to be reverted alongside the
  code (both are already version-controlled), and Railway's healthcheck-gated deployment model
  (demonstrated repeatedly throughout OPS-RAILWAY-ROOT-001) means a failed Phase 2 deployment
  attempt would not, by itself, take the live service down — the previous working deployment
  continues serving until a new one passes its health check.
- Import-boundary tests (`tests/architecture/`) and `ADR-004`'s one-way dependency rule are
  unaffected in content — they govern relationships *among* the root-level packages, which do
  not change under this option — but their own file paths and any `backend/`-relative
  assumptions in the test suite need a Phase 2 audit.
- The `docs/architecture/` (backend-specific ADR series: `ADR-001` through `ADR-004`) and
  `architecture/` (root-level ADR series) documentation split, itself a minor instance of the
  same "two roots" pattern this ADR addresses at the code level, is out of scope for Phase 2
  unless the Founder wants it folded in — noted here as a related but non-blocking observation.

## Explicit questions answered

- **Can `backend` remain the deployable application while shared packages become installable
  internal packages?** Yes, under Option 2 or Option 4 — both were evaluated and rejected in
  favor of Option 3, for the concrete, ASA-specific reasons above (no real per-package
  dependency-resolution need; Railpack risk not actually removed, only reformalized).
- **Is a true monorepo workspace justified?** Not currently — the workspace's central value
  (independent, conflict-checked dependency resolution across packages with real third-party
  requirements) doesn't apply when 18 of ASA's packages have zero third-party dependencies
  between them. Revisit if that changes.
- **Is a single root Python project the simplest solution?** Yes, and it is also the option
  with a concrete, working precedent already in this codebase's own lineage (Stonk).
- **Which option best matches Railway's intended deployment model?** Option 3 — Railway's own
  documentation's "isolated monorepo" pattern is exactly "one directory, one deployable app,"
  which Option 3 makes true again for the whole repository, not just a subtree.
- **Which option best matches long-term maintainability?** Option 3 — one dependency graph,
  one lockfile, one package root, no vendor-sync guard test to keep green, no naming
  collisions, no `PYTHONPATH` to explain to a new contributor.

## Open Questions

- Whether `backend/tests/` merges into the root `tests/` directory or remains a separate
  suite under the new `asa/` location is a Phase 2 implementation detail, not resolved here.
- Whether `docs/architecture/` (backend-specific ADRs) and `architecture/` (root-level ADRs)
  should also consolidate is noted above but explicitly out of this ADR's scope.
- Whether issue #178 (Railpack pip-mode install target) is *fully* resolved by removing its
  structural precondition, or whether some residual risk remains, can only be confirmed by an
  actual Phase 2 deployment attempt — this ADR predicts resolution based on Stonk's working
  precedent but does not claim certainty.

## Documentation Impact

`architecture/ADR-004-repository-organization.md`'s module list and dependency rule are
unchanged by this decision — this ADR is additive to it, not a revision. A Phase 2
implementation should add a short cross-reference from `ADR-004` to this document once
executed, noting that the module boundaries `ADR-004` defines now live under one installable
project root rather than two.

## References

- `project/reports/OPS-RAILWAY-ROOT-001.md` / `.json` — the investigation that surfaced this
  ADR's problem statement, including issue [#178](https://github.com/jaiaFoster/ASA/issues/178)
  (still open, addressed by this ADR's recommendation but not yet confirmed resolved).
- `docs/sprints/SPRINT-008.yaml` (GOV-008A) — the Founder direction ("single execution graph
  and a single source of truth") that this ADR's recommendation is the most literal reading of.
- `architecture/ADR-004-repository-organization.md` — the root-level package boundary and
  one-way dependency rule this ADR preserves unchanged.
- `docs/architecture/ADR-002-composition-root.md` — `backend/`'s (soon: the root project's)
  own composition-root pattern, unaffected by this decision.
- `backend/tests/market_data_ops/test_vendor_sync.py` — the vendor-sync guard this ADR's
  recommendation would retire.
- `/Users/jaiafoster/Claude/stonk` — ASA's migration predecessor, the concrete precedent for
  Option 3's single-flat-project shape deploying successfully to Railway.
- `docs/sprints/ARCH-MONOREPO-001.yaml` (GOV-009, #180) — this document's own Phase 1
  activation record.
