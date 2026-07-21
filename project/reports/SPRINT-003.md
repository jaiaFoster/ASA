# SPRINT-003 Final Report — Strategy Library Extraction

**Status:** Complete  
**Completed:** 2026-07-21  
**Final technical commit:** `64f3871a01a500a9bb68a9b655e139f77c5a4fc1`

## Sprint summary

SPRINT-003 extracted the bounded strategy intelligence from legacy Stonk revision
`5f3fec846f70e9739cf3f15695fd587f0604344c` into ASA's deterministic Strategy Core.
The result is four canonical manifests, eighteen pure Components in two static plugins,
immutable financial contracts, behavioral-equivalence evidence, and an official typed Strategy
Library. No legacy application, provider topology, broker access, persistence, mutable state,
presentation code, or compatibility runtime was copied.

## Completed work

| Work | PR | Merge commit | Result |
|---|---:|---|---|
| Sprint activation | [#91](https://github.com/jaiaFoster/ASA/pull/91) | `14e8de3` | Bounded SPRINT-003 delegation |
| STONK-001 inventory | [#92](https://github.com/jaiaFoster/ASA/pull/92) | `e67a75e` | Four strategies and shared patterns cataloged |
| ARCH-005 specification | [#94](https://github.com/jaiaFoster/ASA/pull/94) | `20f88fb` | Financial domain contracts frozen |
| ARCH-005 contracts | [#95](https://github.com/jaiaFoster/ASA/pull/95) | `cd0d4b0` | Immutable canonical financial types |
| STONK-002 components | [#96](https://github.com/jaiaFoster/ASA/pull/96) | `b0c6000` | Shared and options Components/plugins |
| STONK-003 manifests | [#97](https://github.com/jaiaFoster/ASA/pull/97) | `b084e1d` | Four executable canonical manifests |
| STONK-004 equivalence | [#98](https://github.com/jaiaFoster/ASA/pull/98) | `f0ed0ea` | Pinned legacy calculation and ownership vectors |
| STONK-005 decommissioning | [#99](https://github.com/jaiaFoster/ASA/pull/99) | `17b14ba` | Legacy runtime boundary proven removable |
| STONK-006 library | [#100](https://github.com/jaiaFoster/ASA/pull/100) | `a70cd0f` | Official immutable Strategy Library |
| STONK-007 validation | [#101](https://github.com/jaiaFoster/ASA/pull/101) | `64f3871` | Integrated production validation matrix |

Founder merged the architecture PRs. Enumerated implementation PRs were self-merged only after
local gates, self-review, and GitHub Architecture Validation passed under the bounded delegation.
That delegation expires with this sprint completion.

## Strategy inventory and library catalog

| Strategy ID | Version | Extracted intent |
|---|---:|---|
| `asa.stonk.earnings_calendar` | `1.0.0` | earnings-window calendar candidate |
| `asa.stonk.skew_momentum_vertical` | `1.0.0` | skew/momentum vertical candidate |
| `asa.stonk.forward_factor_calendar` | `1.1.0` | forward-volatility double-calendar candidate |
| `asa.stonk.stock_momentum` | `1.0.0` | deterministic momentum candidate universe |

The Component vocabulary covers evidence gating, universe filtering/capping, weighted scores,
verdicts, earnings windows, expiration selection/projection, implied forward volatility,
forward factor, liquidity, delta selection, calendar/vertical/double-calendar construction, and
option-structure debit. Ranking remains owned by the Ranking Engine; portfolio allocation remains
owned by the Portfolio Engine.

## Architecture and deterministic behavior

Financial contracts use canonical instrument identities, immutable observations/evidence,
deterministic collection ordering, Decimal values, and explicit time. Strategy Manifests are the
only migrated execution definitions. Plugins add a finite statically registered vocabulary and
cannot mutate the runtime. The Strategy Library orders and identifies manifests by content.

Behavioral vectors reproduce the legacy forward factor (`0.20`), calendar debit (`0.3` mid,
`0.5` conservative), vertical conservative debit (`1.3`), strike selection, and candidate
thresholds. Intentional refinements replace floats with Decimal, implicit time with explicit
evidence time, local ranking/allocation with canonical ASA engines, and hidden forward-IV input
with a pure derivation that fails closed for invalid variance.

## Validation results

Final validation on clean technical `main` at `64f3871`:

| Gate | Result |
|---|---|
| Complete repository suite | **1,733 passed, 1 established conditional skip** |
| STONK production matrix | **Passed for all four manifests** |
| 200 uncached whole-graph executions | **Passed under five-second regression ceiling** |
| Deterministic replay and identities | **Passed** |
| Trace and provenance completeness | **Passed** |
| Static plugin and Component isolation | **Passed** |
| Scoped Ruff for sprint production/tests | **Passed** |
| Lean pre-push checks | **All 5 passed** |
| Entrypoint and frozen-governance integrity | **Passed** |
| `git diff --check` | **Passed** |

Every sprint PR's GitHub Architecture Validation passed. The one skipped test is an established
conditional POS test outside Strategy Core. Repository-wide Ruff and naïve root MyPy still expose
pre-existing baseline/configuration failures outside this sprint; open Issue
[#77](https://github.com/jaiaFoster/ASA/issues/77) tracks the Ruff baseline.

## Complexity and change summary

From the SPRINT-002 completion base through STONK-007: **29 files changed, 5,149 additions, 5
deletions**. New abstractions are limited to frozen financial contracts, extracted Components,
two static plugins, four manifests, and the immutable Strategy Library catalog. No adapter,
repository, queue, worker, database schema, API, broker client, deployment configuration, or
alternate runtime was introduced.

## Discovered and resolved defects

- Strategy extraction initially lacked canonical options/earnings/volatility contracts; ARCH-005
  froze and implemented them before migration continued.
- The first Forward Factor manifest expected an already-derived implied forward IV. STONK-004
  moved that strategy-owned calculation into a pure versioned Component and added fail-closed
  regression coverage.
- Exact legacy quote vectors replaced merely representative pricing fixtures during self-review.
- Trace validation now distinguishes start events from completed events carrying output identity.

## Remaining issues and risk

Open Issues #39–#55 remain upstream calibration, reconciliation, evidence, and identity findings;
they were not expanded into this sprint. Issue #77 tracks repository-wide lint debt. The extracted
strategies preserve deterministic mechanics, not demonstrated investment efficacy. Backtesting,
calibration, live market acquisition, broker integration, paper/live trading, and visual authoring
remain explicitly absent and require separately governed work.

## Recommendation and final disposition

Founder should verify the catalog, equivalence matrix, and boundary decisions before authorizing
another sprint. SPRINT-003 is complete: all enumerated tickets are merged, `main` is green, the
legacy runtime is unnecessary, and the official ASA Strategy Library is deterministic, immutable,
replayable, explainable, and isolated from providers and operations.
