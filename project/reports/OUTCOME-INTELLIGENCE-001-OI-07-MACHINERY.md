# OUTCOME-INTELLIGENCE-001: OI-07 Data-Value and Program-Closure Machinery

- **Ticket:** OI-07, plus the program closure required by `docs/sprints/OUTCOME-INTELLIGENCE-001.md`
- **Risk:** R1. Read-only tooling and declared registries; no runtime, API, or schema change.
- **Status:** **machinery complete; OI-07 NOT passed; program NOT closed.** Verdicts are computed from evidence and are currently `evidence_insufficient` / `observation_pending` (see "Current state").

## Why machinery first

The observation corpus is the input to OI-07 and to program closure; it is not a prerequisite for building them. Closing now requires only these steps:
1. Accumulate session captures.
2. Re-run the two generators.
3. Commit their outputs.

No future observation is fabricated. The generators refuse a passing verdict until the evidence exists.

## Components (`tools/outcome_intelligence/`)

| Module | Role |
|---|---|
| `session_capture.py` | One read-only capture per session. It composes three existing collectors: the OT-06 funnel census (every active option row), the OP-07 trade-card traversal and the SP-06 stock-proposal observation. It adds a forward-outcome ledger read. It checks the exact deployed SHA and never mutates anything. |
| `reason_taxonomy.py` | Classifies every typed reason once: `provider_capability` (with capability, data-adequacy gap, and whether paid data could resolve it), `market_structure_or_policy`, `strategy_semantics`, or `asa_internal`. Unknown reasons are `unclassified` and are never silently attributed. |
| `data_value.py` | Builds the deterministic OI-07 report: opportunity counts by strategy, loss attribution by cause and capability, forward-outcome sample sizes, blocked decisions, and quantified paid-capability gaps. |
| `program_closure.py` | Produces AOY and coverage metrics, the evidence gates, and the closure report in the section order the program prompt requires. |

**Declared inputs** (`project/research/OUTCOME-INTELLIGENCE-001/`):
- `blocked-decisions-v1.json` lists decisions BD-01 to BD-08. Each is tied to on-disk evidence and to data-adequacy gaps. The tool rejects missing references and gaps it cannot recognise.
- `program-closure-inputs-v1.json` holds sprint states, carried targets, open corrections, and the next product decisions ND-01 to ND-03.

## Rules the code enforces

- **Eligible session:** a US equity session whose latest capture was taken after that session's close. Intraday and non-session captures are reported with their reason but do not count. When several captures exist for one session, the latest is used.
- **AOY:** complete, currently actionable proposals per eligible session, reported as total, options and stocks. Option actionability is the funnel terminal `actionable_opportunity`. Stock actionability is a stock proposal with status `actionable`. The split keeps a daily stock benchmark from silently inflating the options metric.
- **Coverage metrics:**
  - evaluation coverage;
  - unexplained drops;
  - strategy evaluation completion rate;
  - constructible rate after qualifying signals;
  - provider-limited rate by capability;
  - median actionable evidence age;
  - trade-card completeness and defects;
  - tracked count and due-horizon outcome coverage.
- **OI-07 `complete` requires all of:**
  - at least 5 eligible sessions (parameter `--minimum-eligible-sessions`, declared default);
  - a readable production outcome ledger;
  - zero unclassified reasons.

  An unreadable ledger is reported by status, never as zero.
- **Program closure gates:**
  - prior sprints closed;
  - forward ledger deployed;
  - at least one observed forward outcome;
  - AOY measured over the minimum eligible sessions;
  - zero unexplained drops;
  - no presentation defects;
  - OI-07 complete;
  - no open corrections.

  Any failing gate gives `reopen_required`. Any pending gate gives `observation_pending`. The best possible verdict is `closure_ready` or `closure_ready_with_downgrades`. The tool never declares the program closed.
- **Downgrades are permanent.**
  - A closure report whose text records a downgrade must be matched by an unmet target.
  - An unmet target requires the state `closed_with_downgrade`.
  - Every rendering prints it as **UNMET (downgraded)** and states "This is not a success".
  - STRATEGY-LIBRARY-001's SL-02 target (2–4 option strategies; 1 achieved) is carried this way. Relabelling it fails validation.

## Operating procedure

After each session close (≥ 16:15 ET):

```
python -m tools.outcome_intelligence.session_capture \
  --base-url https://asa-production-b2c4.up.railway.app \
  --production-sha <deployed release_sha> \
  --output project/observations/ASA-OPTIONS-TO-OUTCOMES-2026Q4/<session_date>.json
```

Then regenerate:

```
python -m tools.outcome_intelligence.data_value \
  --captures project/observations/ASA-OPTIONS-TO-OUTCOMES-2026Q4 \
  --output-json project/reports/OUTCOME-INTELLIGENCE-001-OI-07.json \
  --output-markdown project/reports/OUTCOME-INTELLIGENCE-001-OI-07.md
python -m tools.outcome_intelligence.program_closure \
  --captures project/observations/ASA-OPTIONS-TO-OUTCOMES-2026Q4 \
  --data-value project/reports/OUTCOME-INTELLIGENCE-001-OI-07.json \
  --output-json project/reports/ASA-OPTIONS-TO-OUTCOMES-2026Q4-CLOSURE.json \
  --output-markdown project/reports/ASA-OPTIONS-TO-OUTCOMES-2026Q4-CLOSURE.md
```

Both exit 2 while the evidence is insufficient.

## Validation

- `tests/tools/test_outcome_intelligence.py` has 12 tests covering:
  - taxonomy extraction, and `unclassified` treated as never guessed;
  - session selection (the latest capture per session; intraday and weekend captures rejected);
  - refusal to complete without evidence;
  - exact counts, attribution, samples and gap quantification;
  - determinism and input-order independence;
  - the unclassified-reason block;
  - registry reference and gap validation;
  - pending gates;
  - `closure_ready_with_downgrades` carrying the SL-02 downgrade;
  - reopen on an unexplained drop;
  - rejection of downgrade relabelling;
  - ledger `outcome_route_not_deployed` distinguished from an empty available corpus.
- `tests/tools` total: 35 passed. ruff and mypy are clean on the new package.

## Current state (first real capture, 2026-09-24 session, `d52146f`)

These are the generated reports, `OUTCOME-INTELLIGENCE-001-OI-07.{md,json}` and `ASA-OPTIONS-TO-OUTCOMES-2026Q4-CLOSURE.{md,json}`. Regenerating them from the committed capture is byte-identical.

- **OI-07:** `evidence_insufficient`.
  - 1 of 5 eligible sessions.
  - Ledger `outcome_route_not_deployed`, because #493 is awaiting the Founder merge.
- **Program:** `observation_pending`.
  - Passing gates: prior sprints closed, zero unexplained drops, no presentation defects, no open corrections.
  - Pending gates: forward ledger deployed, forward outcome observed, AOY over 5 sessions, OI-07 complete.
- **AOY (n=1):** 3.
  - Options: 2 (earnings_calendar/CI and spy_put_credit_spread/SPY).
  - Stocks: 1 (B001/SPY).
- **Coverage:**
  - Evaluation coverage 1.0.
  - Constructible rate after qualifying signals 0.4.
  - Median actionable evidence age at close about 330 s.
- **Loss attribution** (1,509 non-actionable rows):
  - 1,093 strategy semantics;
  - 382 market structure or policy, which paid data cannot change;
  - 34 provider capability: earnings 19, option chain 11, quote 3, historical bars 1.
- **Unmet target:** STRATEGY-LIBRARY-001 SL-02 is carried as **UNMET (downgraded)**.
- **Forward corpus:** growth depends on ND-01. The Architect APPROVED-WITH-AMENDMENTS system auto-enrollment (`OUTCOME-INTELLIGENCE-001-ND-01-ARCHITECT-DECISION.md`). It requires migration 0020, which means a separate R3 PR after #493 and a Founder merge.
