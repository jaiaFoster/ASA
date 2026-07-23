# OPS-RAILWAY-ROOT-001 — Restore Repository-Root Railway Deployment

Status: **Partially complete, blocked on an unresolved Railway/Railpack platform issue**.
Per this ticket's own `docs/sprints/OPS-RAILWAY-ROOT-001.yaml` (Founder Sprint Delegation,
GOV-AMD-001-013 / GOV-008B, #167), three genuine, distinct bugs in this repository's own
Railway configuration were found and permanently fixed, and the deployment now progresses
further than it ever has (a full, successful image build for the first time). The final
blocker -- the deployed container's Python cannot see the packages Railpack's pip-mode
install step puts somewhere -- could not be resolved from this side and is filed as
[#178](https://github.com/jaiaFoster/ASA/issues/178) for Founder decision. The previous,
`/backend`-scoped deployment remained live and healthy throughout this entire
investigation (confirmed repeatedly via `GET /api/v1/health` -> `200 {"status":"ok"}`) --
this was never a production incident.

Investigation window (UTC): 2026-07-23, approximately 01:30–03:30
Repository commit (current, `main`): `94a95df`

## 1. Root cause analysis

Four distinct problems were found, in the order they were uncovered (each one blocked
visibility into the next):

1. **A custom Railpack install step lost its default input wiring.** `railpack.json`'s
   `steps.install.commands` override (added in PR #166 to defend against Railpack detecting
   an unrelated root-level `pyproject.toml`) fully replaced Railpack's auto-generated install
   step, including whatever implicit `inputs` wiring gives that step access to the copied
   repository files. The step ran against a completely empty working directory --
   `pip install -r requirements.txt` failed with "No such file or directory" instantly,
   `BUILD_IMAGE` failing in ~5 seconds with no error text retrievable via any log API.
2. **Railway's startCommand/preDeployCommand parser rejects bash control-flow syntax.** An
   intermediate fix guarded `cd backend` with an `if [ -d backend ]; then ...; fi`
   conditional (defending against an unconfirmed cwd-ambiguity hypothesis). Railway's parser
   rejected it outright ("Failed to parse start command") -- it is a restricted command
   parser, not a full shell.
3. **A root-level `uv.lock`/`pyproject.toml` pair made Railpack briefly select the wrong
   package manager and the wrong project's dependencies.** Once the broken install step (item
   1) was removed and Railpack's own default install step restored, its detection correctly
   found `backend/`'s FastAPI/pip signals on some runs, but a root-level `pyproject.toml` +
   `uv.lock` (belonging to `tools/deployment_observer/`'s own dev tooling, `dependencies=[]`,
   only `mypy`/`pytest`/`pyyaml`/`ruff` in its dev group) was also present at the same
   directory level once `rootDirectory` widened to the repo root. On one deploy, Railpack
   selected `uv` and ran `uv sync --locked --no-dev --no-editable` against *that* project
   instead of `backend/`'s real dependencies, producing a venv with none of them (`No module
   named alembic`). Confirmed via `railpackInfo.metadata.pythonPackageManager` flipping
   between `"pip"` and `"uv"` across otherwise-identical deploys, and via a captured build log
   fragment showing the `uv sync` invocation directly.
4. **Railpack's pip-mode install target is not on the runtime container's `sys.path`
   (UNRESOLVED).** After relocating the deployment-observer's `pyproject.toml`/`uv.lock` out
   of the repo root (eliminating item 3's ambiguity for good), the build succeeds
   consistently and `pythonPackageManager` correctly and consistently reports `"pip"`. But
   the deployed container's `python` resolves to Railpack's raw mise-managed interpreter
   (`/mise/installs/python/3.12.13/bin/python`), and a diagnostic `python -m site` run inside
   that container shows `sys.path` contains no venv at all -- only `/app/backend`,
   `/app/backend/src`, `/app`, and mise's own site-packages -- with
   `USER_SITE: '/root/.local/lib/python3.12/site-packages' (doesn't exist)`. This strongly
   suggests Railpack's pip-mode provider installs via something equivalent to
   `pip install --user`, landing packages somewhere that isn't copied into the runtime image.
   No documented Railpack or Railway configuration field controls this. Filed as
   [#178](https://github.com/jaiaFoster/ASA/issues/178).

## 2. Why the previous configuration failed

Before this ticket, `rootDirectory` had already been changed from `/backend` to `.` (API-001,
GOV-008A) so the deployed process could import root-level shared packages (`screening/`,
`analytics/`, `strategies/`, `market_data/`, `domain/`). That change alone was correct in
intent, but two deploy attempts made before this ticket's activation both failed at
`BUILD_IMAGE` with no retrievable error text -- the cause (item 1 above) was only diagnosable
once this ticket's delegation allowed direct, iterative live investigation.

## 3. Files changed

- `railpack.json`: reduced to pinning `provider`/`packages.python` only -- the custom
  `steps.install.commands` override (item 1) was removed entirely, restoring Railpack's own
  default, correctly-wired install step.
- `backend/railway.json`: `preDeployCommand`/`startCommand` went through several live-tested
  intermediate forms (a cwd guard, PATH prepends, diagnostic probes) before settling back on
  the plain, original form -- none of the intermediate mitigations proved necessary or
  effective once items 1 and 3 were actually fixed.
- `pyproject.toml`, `uv.lock` -> moved to `tools/deployment_observer/pyproject.toml` /
  `tools/deployment_observer/uv.lock` (item 3's fix). Confirmed via all three relevant
  workflows (`validate-architecture.yml`, `validate-pos.yml`,
  `railway-deployment-observer.yml`) that nothing installs via `uv`/`pip` from the root-level
  location -- it was pure local-dev convenience, safe to relocate.
- `tests/deployment_observer/test_workflow.py`: `WORKFLOW_PATH` anchored to `Path(__file__)`
  instead of a bare relative string, which only worked because `pyproject.toml` (and hence
  pytest's implicit rootdir) used to sit at the repo root.
- `backend/tests/test_railway_runtime.py`: added a second production-command subprocess test
  proving the command works when `cwd` starts already inside `backend/` (added alongside the
  cwd-guard mitigation, later removed alongside it once that mitigation proved unnecessary);
  final state matches the plain, original command form.
- A Railway service environment variable, `PIP_USER=0`, was set live as a mitigation attempt
  for item 4 -- confirmed to have no effect (see below), left in place (harmless, has no
  observed effect either way).
- `docs/sprints/OPS-RAILWAY-ROOT-001.yaml`: this ticket's own Founder Sprint Delegation
  activation record (GOV-008B, #167).

Pull requests, in order: #168 (cwd guard, later reverted), #169 (install-step fix), #170
(cwd guard revert), #171 (deployment-observer relocation), #172–176 (diagnostic bisection
sequence, all reverted or superseded), #177 (final cleanup, current state).

## 4. Explanation of the permanent fix

Items 1–3 above are genuinely fixed and permanent -- confirmed by the deployment progressing
past `BUILD_IMAGE`/`PUBLISH_IMAGE` consistently on every subsequent attempt, something that
never happened even once before this ticket's work. Item 4 has **no fix from this side**:
every lever available through `railway.json`, `railpack.json`, and Railway service
environment variables was tried (PATH prepends, a `PIP_USER=0` variable, a custom install
step with explicit filesystem diagnostics) without success, and Railway's own build logs do
not expose the actual `pip install` invocation or output through any API or MCP tool
available for inspection. This is documented as a platform-level limitation in #178, not a
repository configuration gap.

## 5. Railway deployment URL

`https://asa-production-b2c4.up.railway.app` (service `43195c7a-8c18-4711-98a8-633d280a3b77`,
environment `production`). Still served by the pre-existing, healthy `/backend`-scoped
deployment throughout this entire investigation -- Railway's healthcheck-gated cutover model
never promoted any of the failed repository-root attempts.

## 6. Smoke test results

- `GET /api/v1/health` -> `200 {"status":"ok"}`, confirmed repeatedly throughout the
  investigation (before, during, and after every deploy attempt) -- the live service was
  never degraded.
- Local subprocess tests (`backend/tests/test_railway_runtime.py`) spawn the exact production
  `startCommand` string as a real subprocess and confirm it runs a real migration and serves
  a real health check successfully when Python and its dependencies are actually resolvable
  (i.e., in this repository's own local dev environment) -- proving the command itself is
  correct; the failure is specific to Railpack's build-time packaging behavior for this
  service, not the command.
- Full backend test suite: 85 passed, 13 skipped (Postgres-marked, no local Docker) as of the
  final commit in this ticket.

## 7. Final deployment status

**Not successful.** The repository-root deployment (`rootDirectory: "."`) builds and
publishes an image successfully and consistently, but every attempt fails at container
startup with `No module named alembic` due to item 4 above. `rootDirectory` remains `.` per
this ticket's own constraint (`do_not_revert_to_backend_deployment`) -- the shared-package
architecture API-001 introduced is fully preserved in the repository's configuration, even
though the live cutover to it has not yet succeeded. The previously-working deployment
continues serving production traffic unaffected.

## 8. Discovered and resolved defects

1. **Broken custom Railpack install step (item 1)**: fixed by removing the override
   entirely (PR #169).
2. **Railway parser rejecting bash conditionals**: discovered and reverted within this same
   investigation (PR #168 introduced it, PR #170 reverted it) -- documented for future
   reference; Railway's startCommand/preDeployCommand parser does not support control-flow
   syntax.
3. **Root-level `uv.lock` package-manager ambiguity (item 3)**: fixed by relocating the
   deployment-observer's dependency files to where the tool they belong to actually lives
   (PR #171) -- a genuine, permanent structural fix, not a workaround.
4. **preDeployCommand's stdout/stderr is not reliably captured by Railway's deploy-log
   stream**, independent of command content -- confirmed by Railway's own support agent
   exhaustively searching every available log filter for a deployment whose preDeployCommand
   had definitely run. `startCommand`'s output, by contrast, was reliably captured across
   every attempt. Documented here for any future diagnostic work on this service.

## 9. Remaining non-blocking issues

- **#178** (new this ticket) -- Railpack's pip-mode install target not on the runtime
  container's `sys.path`; blocks the repository-root deployment's actual cutover. Requires
  either a Railway support resolution or further investigation the Founder authorizes
  separately (a custom install step with explicit `--target`/`--no-user` flags, now armed
  with a correct understanding of Railpack's `inputs` wiring from item 1, is one untested
  option).
- **#147** (carried over, unrelated) -- CI coverage gaps for root-level mypy and some test
  paths; not touched by this ticket.
- **#162** (carried over, unrelated) -- live data-freshness gate; not touched by this ticket.

## 10. Recommendations

1. Open a Railway support thread (`station.railway.com`) referencing service
   `43195c7a-8c18-4711-98a8-633d280a3b77` and the diagnostic deployment
   `96d1f190-f595-4ede-b8a5-c67209466e3c`, asking them to inspect the actual Metal builder's
   `pip install` output -- the one piece of evidence unavailable through any tool this
   investigation had access to.
2. Alternatively, attempt a custom `railpack.json` install step with an explicit
   `pip install --no-user --target=<mise site-packages path> .` (or equivalent), now that
   this investigation understands why the earlier custom-install-step attempt broke (missing
   `inputs` wiring) -- untested as a fix for item 4 specifically.
3. If neither is prioritized soon, the previous `/backend`-scoped deployment continues to
   serve production safely indefinitely; there is no urgency from an availability
   perspective, only from API-001's own goal of exposing the shared execution-graph
   architecture to the deployed service.

## 11. Confirmation: no secrets exposed

No credential values were read, printed, exported, or committed at any point in this
ticket's work. The one live infrastructure mutation beyond `railway.json`/`railpack.json`
commits -- the `PIP_USER=0` environment variable -- was set via Railway's own service
configuration API (value never seen by the implementing agent, consistent with this
project's established secret-handling pattern) and contains no secret material itself.

## 12. Deliverables

- `project/reports/OPS-RAILWAY-ROOT-001.md` / `.json` -- this report.
- `railpack.json`, `backend/railway.json`: corrected, permanent configuration for items 1–3.
- `tools/deployment_observer/pyproject.toml`, `tools/deployment_observer/uv.lock`: relocated
  from the repository root (item 3's fix).
- `tests/deployment_observer/test_workflow.py`, `backend/tests/test_railway_runtime.py`:
  updated/hardened tests reflecting the final state.
- `docs/sprints/OPS-RAILWAY-ROOT-001.yaml`: the Founder Sprint Delegation record (#167).
- Issue [#178](https://github.com/jaiaFoster/ASA/issues/178) (new, logged for Founder
  decision on the remaining blocker).
