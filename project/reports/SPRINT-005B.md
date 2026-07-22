# SPRINT-005B — Market Data Platform Implementation

Status: Founder verification pending after MD-020.

## Sprint summary

SPRINT-005B implements the frozen provider-agnostic Market Data Platform: immutable observations,
centralized secret-safe configuration, provider ports/factory/registries, bounded request budgets,
deterministic fixture data, diagnostics, read-only Tradier/Finnhub/Alpha Vantage adapters, explicit
fallback, non-statistical resolution, sealed snapshots, offline replay, compliance tests, generated
documentation, an operations runbook, and a legacy migration assessment.

## Merged pull requests

| Ticket | PR | Merge commit |
|---|---:|---|
| MD-001 | #113 | `182c4f00d853aa220c87358e2665aa6573cd450a` |
| MD-002 | #114 | `d638dfb0ed36a76be1c718e71bfaa6269c21c946` |
| MD-003 | #115 | `486a73cac8eb4685ad77fb5f104020079145e7ff` |
| MD-004 | #116 | `d65ad50a0c8e91e18538277dd2fd5d58ea2926b8` |
| MD-005 | #117 | `44bc6b00137de6bf1ae99f2285be89e191e77545` |
| MD-006 | #118 | `f85063653c1e708539e9f2e65833055eded9242e` |
| MD-007 | #121 | `df32baf960781f7b45c0629ff8ba3c7b89b2440c` |
| MD-008 | #122 | `9855a151ea972b6bea71a774bc37c12ea644b60a` |
| MD-009 | #123 | `28194c36a83f6facc81510cb7e26ed7e2e517e22` |
| MD-010 | #124 | `57834b85029c289cfbf0707e5f1982a090db01c4` |
| MD-011 | #125 | `bea89b0f5ada22fc578248f60ce2dd0d9b540ab2` |
| MD-012 | #126 | `63d274bb3333e1a0339553a3f7e3dc9c0b9cb765` |
| MD-013 | #127 | `068528e064eda80d53e494ffe0fb53f41e05a4e2` |
| MD-014 | #128 | `8b1c18997bd9e2ef5d5895e2c9506d380228ba9b` |
| MD-015 | #129 | `e3ce728673c3c1eebe4ebf4442b15dca6c800b29` |
| MD-016 | #130 | `dd238323616fae474170e326791bbe4ab50e9fbe` |
| MD-017 | #131 | `ab4c5a82f180c43e91e113d25be185e992c0a321` |
| MD-018 | #132 | `9fd071c1a3da64dfc175f0694cc8f688c3873fed` |
| MD-019 | #133 | `9485db9600cca2d196b1aca9ca4c5888930e3020` |

Architecture prerequisites: SPRINT-005A PR #110, ARCH-007A PR #112, ARCH-007B PR #120.

## Architecture and safety verification

- Canonical observations are immutable, provider-neutral, provenance-aware, decimal-safe, UTC,
  and serializable.
- Strategies request canonical capabilities; provider priority is configuration-driven.
- `MarketDataSubject` owns analytical identity and explicit provider address projections.
- Provider SDK/payload objects do not cross adapters; all adapters are read-only.
- Every live request requires finite authorization; retries consume budget.
- Fallback records every attempt and never silently substitutes stale or cross-capability data.
- Resolution selects one provider-reported value by frozen priority or remains unresolved. Median,
  averaging, voting, confidence blending, and other statistical synthesis are absent.
- Snapshot identity is content-derived under `asa.market_snapshot/v1`.
- Replay accepts sealed snapshots only and cannot construct providers or network transports.
- No database schema, persistent cache, brokerage mutation, or execution behavior was introduced.

## Integrated evidence

MD-020 exercises fixture acquisition across quote, historical bars, earnings, and option-chain
capabilities through fulfillment, resolution, snapshot construction, digest verification, and
offline replay. Provider fixtures separately cover Tradier success, Finnhub candle success/no-data/
empty/entitlement paths, Alpha Vantage throttling, explicit fallback, all-provider failure, budget
exhaustion, secret redaction, documentation drift, and replay network prohibition.

Final command results are recorded in the MD-020 pull request. The expected live-provider test class
is disabled in normal CI; all offline validation is credential-free and network-free.

Final offline validation produced 1,900 passing tests and 2 established skips (the conditional POS
fixture and the deliberately default-off live-provider sentinel). Market-data/domain strict MyPy
passed across 36 source files. Sprint-scope Ruff, architecture tests, replay checks, generated-doc
drift, Lean entrypoint/integrity/pre-push, secret scan, and `git diff --check` passed. Repository-wide
Ruff still reports the pre-existing unused `Protocol` import in
`providers/synthetic/deterministic_provider.py`; this is outside SPRINT-005B and remains part of the
historical lint baseline tracked by Issue #77.

## Provider contract results

One reusable compliance evaluator passes every declared fixture-covered capability for:

- deterministic fixture: quote, historical bars, earnings, option chains;
- Tradier: quote, historical bars, option chains/contracts/Greeks/liquidity;
- Finnhub: quote, historical bars, earnings;
- Alpha Vantage: historical bars and earnings.

## Live validation and Finnhub candle diagnostic

`ASA_TRADIER_ACCESS_TOKEN`, `ASA_FINNHUB_API_KEY`, and `ASA_ALPHA_VANTAGE_API_KEY` were absent from
the authorized worker environment. No live call was attempted. This is an external validation
blocker, not an offline implementation failure.

Finnhub's offline diagnostic matrix proves request resolution `D`, explicit UTC ranges, semantic
status checks, equal non-empty arrays, timestamp normalization, rate-limit mapping, and distinct
`no_data`, `empty_payload`, `schema_mismatch`, authentication, entitlement, transport, timeout, and
provider-unavailable failures. Live entitlement/candle availability remains externally unverified.

## Documentation and operations

Generated pages under `docs/providers/` include the capability matrix, configuration names, rate
limits, validation use, limitations, and fixture coverage. Architecture CI rejects drift. The
provider diagnostics runbook defines preflight, bounded execution, failure interpretation, Finnhub
candle diagnosis, safe retry, retention, and escalation.

## Legacy migration outcome

The Stonk assessment classifies provider knowledge and safe normalization as migrate; direct env
reads, silent fallback, provider objects, strategy-owned fetches, and SQLite coupling as replace;
obsolete wrappers, secret-bearing output, and duplicated paths as retire; and persistence, news,
reference/corporate-action data, streaming, and brokerage ingestion as defer.

## Remaining issues and recommendations

1. Founder supplies provider credentials only in an authorized environment and reviews subscription
   terms before bounded live validation.
2. Run the documented Tradier, Finnhub, and Alpha Vantage minimum live subsets; retain only
   secret-free reports.
3. Do not authorize a successor sprint implicitly. Persistence, licensing/retention, production
   cache, news, corporate actions, calendars, reference data, and streaming need separate scope.

## Complexity delta

Relative to the merged SPRINT-005A architecture baseline, SPRINT-005B changes 64 tracked files with
9,040 added and 8 deleted lines before this completion record. The delta is dominated by immutable
contracts, provider adapters, deterministic fixtures/tests, generated provider documentation, and
operational evidence. New abstractions map directly to frozen architecture: provider ports/factory/
registries, budget accounting, validation, fulfillment, resolution, snapshot, replay, compliance,
and documentation generation. No generic repository, dynamic plugin, persistent cache, background
worker, database schema, or compatibility layer was added.

## Risk assessment

Residual risk is external-provider behavior: credentials, entitlements, subscription limits,
availability, and licensing were not observable offline. Structural risk is bounded by fixture
contract coverage, explicit normalized failures, finite budgets, no silent fallback, immutable
snapshots, and network-impossible replay.
