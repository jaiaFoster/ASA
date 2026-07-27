# SPRINT-010 — Screening Reliability & Product Surface

**Final verdict: FOUNDER_BLOCKER**  
**Implementation:** complete and merged through LEGACY-001  
**Production deployment:** successful at `c5ac2596e01d33f4d558be3781aaaac72e533ccf`  
**Blocker:** authenticated production URL/token context is unavailable to this worker

## Root cause and changed behavior

| Ticket | Root cause | Result |
|---|---|---|
| REL-001 / PR #223 | Earnings acquisition used a zero-width request and rejected useful degraded fallback data. | Uses a bounded 75-day window, validates provider semantics, and accepts explicitly degraded usable evidence. |
| REL-002 / PR #224 | Forward Factor trusted one expiration pair and Tradier used the first chain row as whole-chain freshness. | Tries at most five ranked provider-listed pairs and uses newest contract evidence for chain time. |
| OPS-001 / PR #225 | Production verification lacked one bounded secret-safe path; CORS omitted `Authorization`. | Added six-step smoke harness, redaction coverage, and correct CORS preflight. |
| LIFE-001 / PR #226 | Opportunity transitions had a contract but no production append/read composition. | Added idempotent append-only Postgres history, refresh/scheduler writes, and paginated replay. |
| SURFACE-001 / PR #227 | Screening reads exposed only the legacy core projection. | Added universal fields, history linkage, filters, pagination, and deterministic non-ranking sorts. |
| LEGACY-001 / PR #228 | Obsolete state/service/table remained as a second dormant authority. | Removed legacy service/repository paths and dropped `screening_state` without backfill. |

## Validation evidence

- Full local repository after LEGACY-001: **2,527 passed, 15 skipped**.
- Focused VERIFY matrix: **91 passed** across all three migrated adapters, authenticated
  API behavior, history, scheduled writes, generic queries, Tradier normalization, and
  operational safeguards.
- LIFE-001 PostgreSQL fix and history integration: Product CI backend green.
- LEGACY-001 migration upgrade/downgrade/upgrade: Product CI backend green.
- PRs #223–#228: Architecture Validation, backend, and frontend checks green before merge.
- Ruff on changed paths, strict mypy for `asa` and `strategy_runtime`, Lean entrypoints,
  governance integrity, pre-push, and `git diff --check`: green.
- Architecture delta search found no new strategy-named conditional in API,
  persistence, or universal runtime. Remaining names are registration/configuration
  data and the operator-selected smoke default.
- Issue #162 was audited. REL-002 resolves its option-chain half; the after-hours quote
  behavior remains open and was documented on the issue.

## Production evidence

GitHub deployment `5616110664` reports success for commit `c5ac259`. Direct,
secret-free probes:

| Probe | Result |
|---|---|
| `GET /api/v1/health` | 200 `{"status":"ok"}` |
| `GET /api/v1/readiness` | 200 `{"status":"ready"}` |
| unauthenticated `GET /api/v1/screening` | 404, fail closed |

The worker environment has neither the production base URL variable nor
`ASA_AGENT_API_TOKEN`; Railway CLI is installed but not linked. Therefore these required
claims remain unverified and are not represented as passing:

- authenticated smoke for earnings_calendar, forward_factor, and skew_momentum;
- at least one non-missing live result with metrics for each strategy;
- live universal-state persistence and cold-start repopulation;
- live opportunity-history append/replay.

This is a Founder access blocker, not an implementation failure. Credentials must not be
placed in chat, a ticket, this report, or repository.

## Founder completion command

In an authorized environment with the token already sealed:

```bash
python tools/screening_smoke.py https://asa-production-b2c4.up.railway.app \
  --signal earnings_calendar --symbol AAPL

python tools/screening_smoke.py https://asa-production-b2c4.up.railway.app \
  --signal forward_factor --symbol AAPL

python tools/screening_smoke.py https://asa-production-b2c4.up.railway.app \
  --signal skew_momentum --symbol SPY
```

Then inspect authenticated aggregate results and the linked earnings opportunity history.
Record only status codes and secret-free normalized output. Never paste the token.

## Risks and rollback

- The remaining open quote-freshness behavior is tracked by issue #162.
- `0007` downgrade recreates the legacy schema empty; it cannot restore dropped rows.
- Roll back individual behavior with the corresponding squash commit. Do not introduce
  dual reads, dual writes, or a backfill compatibility path.

## Sprint delta

Through LEGACY-001: **46 files changed, 1,359 lines added, 1,260 deleted** relative to
the activation commit. No governance, constitutional, trading, sizing, portfolio,
provider, or dashboard scope was added.

SPRINT-010 remains **Founder verification pending** until the authenticated production
matrix supplies the four missing live proofs above.
