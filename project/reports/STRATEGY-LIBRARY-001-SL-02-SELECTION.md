# STRATEGY-LIBRARY-001 — SL-02 options-wave selection

Research packet produced read-only on main@5553ac7; C1 source rules re-verified verbatim by the worker on 2026-09-24. Decision: implement **C1** now (`spy_put_credit_spread`); **C2 (Cboe CNDR)** requires an Architect decision on index-underlying, root/settlement identity, and Black-delta fidelity before intake; SPY substitution for CNDR is prohibited. Stock wave (SL-03): `stock_momentum` skipped — see `docs/strategies/intake/stock_momentum.md`.


## What ASA can represent today

- **Structures.** `StructureKind` has NONE, VERTICAL, CALENDAR and CUSTOM (`strategy_runtime/contract.py:147`).
  - `OptionStructureIntent` and `ExecutableStructureAssessment` accept only CALENDAR or VERTICAL, with exactly 2 legs (`option_structure_resolver.py:59-64`, `executable_structures.py:119`).
  - Any other leg shape resolves as CUSTOM, which is reported as `DIFFERENT_STRUCTURE_AVAILABLE`, never as a silent substitute.
  - Multi-leg packages already exist as compositions of 2-leg structures (`DoubleCalendarStructure`, `stonk_components.py:1461`).
  - `OptionStructureType` has STRADDLE, STRANGLE, DIAGONAL and CASH_SECURED_PUT, but these are domain-only and not executable.
- **Capabilities.** Production providers cover the following:
  - Tradier: quotes, bars, and `OPTION_CHAIN_V1` with greeks (delta, `mid_iv`, bid/ask, OI, volume).
  - Finnhub: quotes, bars, `EARNINGS_CALENDAR_V1`.
  - **Not acquired:** historical IV / IV Rank (`VolatilityEvidence.iv_rank` has no producer), T-bill rates, index-underlying modelling (`InstrumentKind` = EQUITY/OPTION/CASH), and option settlement style or root.
- **Universe.** `APPROVED_LIVE_UNIVERSE` has 30 symbols, including SPY, QQQ and IWM (`screening/live_acquisition.py:88`), plus the SP500 cohort. SPX is not in it.
- **Reusable pieces.**
  - `VerticalStructure` (long/short delta targets), `OptionStructureDebit` (signed, so a negative value is a credit), `OptionStructureCollectionLiquidity`, `RequiredEvidenceGate`, `VerdictClassifier`, and the core `compare`/`boolean_and`.
  - Derived facts `SPREAD_QUALITY`, `OPEN_INTEREST_QUALITY` and `OPTION_VOLUME_BAND`, plus `option_payoff`.
- **Existing strategies to differ from.**
  - Earnings calendar (long vol into an event).
  - Forward factor (term-structure double calendar).
  - Skew momentum (directional debit vertical).
  - None of them sells premium on a schedule.

## Candidates

### C1: Option Alpha SPY 30-DTE Put Credit Spread (Backtest 1, hold to expiration)

- **Source:** Kirk Du Plessis, Steve Henry and Ryan Hysmith, "8 SPY Put Credit Spread Backtest Results Analyzed". Published 2021-11-17, updated 2023-01-11. https://optionalpha.com/blog/spy-put-credit-spread-backtest

| Item | Source rule (quoted where possible) | ASA representation |
|---|---|---|
| Underlying | "sequentially opened bull put spreads on SPY" | SPY only. QQQ and IWM are not in the source. |
| Entry gate | None. Unconditional, with "Only one position active at any time" | Always evaluable. The one-position rule is portfolio state, not screener semantics, so it is shown as a disclosed limitation. |
| Expiration | "30 days to expiration" | The expiration nearest 30 calendar DTE. An equidistant tie gets a typed terminal reason, never a chosen side. |
| Strikes | "0.30 delta for the short contract and 0.10 delta for the long contract" | `VerticalStructure(option_type=put, short=0.30, long=0.10)`, nearest absolute provider delta. |
| Width | "$5-wide" is given as an illustrative example only | Width follows from the delta rule. It is not a gate. |
| Exit | "Hold the position to expiration" | Lifecycle label. No management. |
| Liquidity / exclusions | None stated | No gates. Liquidity is shown as a diagnostic only. |
| Variants 2–4 | 50%/75% targets, 25%/50% stops, 15 DTE, rolling | **Excluded.** The stop-loss base is never defined. |

- **Capabilities:** `OPTION_CHAIN_V1` (delta, bid/ask) and `REAL_TIME_QUOTE_V1`. **All acquired**, and SPY chains are already requested by forward factor and skew momentum, so the demand is shared.
- **Structure fit:** VERTICAL, 2 legs, short put above long put. The resolver's `_shape` accepts it as it is.
- **Reuse:**
  - Components: `VerticalStructure`, `OptionStructureDebit` (as net credit), `option_payoff`, and the liquidity diagnostics.
  - New component: a single-expiration nearest-target-DTE selector. The existing selectors are pair-based.
  - New derived facts: `vertical_max_loss = width − credit` and `credit_to_width`, each with a formula_id.
- **UNKNOWN:**
  - No delta at the target expiration → `missing_actual_delta`.
  - No expiration → `no_expiration_near_target`.
  - A DTE tie → `ambiguous_expiration_tie`.
  - Missing bid or ask → conservative credit is UNKNOWN.
  - Long and short legs resolve to the same strike → `no_compatible_contract`.
- **Verdict: RECOMMEND.**

### C2: Cboe S&P 500 Iron Condor Index (CNDR)

- **Source:** Cboe Global Indices, *CNDR Methodology*, v4.1, revised 2025-12-12. https://cdn.cboe.com/api/global/us_indices/governance/CNDR_Methodology.pdf

| Item | Source rule | ASA representation |
|---|---|---|
| Entry timing | Roll date is "the third Friday of each month". If that is a holiday, the preceding business day. Strikes are selected before 11:00 ET. | Roll-date gate from `market_data/session_calendar.py`. No provider supplies `TRADING_CALENDAR_V1`. Other days get `not_roll_date`. |
| Expiration | Monthly, AM-settled SPX. "1 month". | Needs the standard SPX root and settlement style. **Not modelled.** |
| Strikes | Short call/put "delta closest to 0.20/−0.20". Long call/put "closest to 0.05/−0.05". Deltas use the **Black formula**, with inputs as of 11:00 ET. | Two VERTICAL intents: a put credit spread (−0.20/−0.05) and a call credit spread (0.20/0.05). |
| Pricing | "average of the last bid-ask quote … before 11:00 a.m. ET" | Midpoint. This matches `midpoint-v1` in intent, but ASA's snapshot time is not 11:00 ET. |
| Quantity | "All option positions are one unit" | Quantity 1. |
| Exit | Settle at SOQ. No management. | Hold to expiration. |
| Collateral | T-bill account = 10 × maximum loss | Allocation is source-defined but needs a T-bill rate, which ASA does not acquire. Shown as UNKNOWN. |

- **Capabilities:**
  - Option chain and quote: acquired.
  - SPX as an index underlying, AM/PM root distinction, T-bill rate: **not available**.
  - Black-model delta: ASA has provider (ORATS) delta only, which can select a different strike at the margin.
- **Structure fit:** a composition of two VERTICALs, following the `DoubleCalendarStructure` pattern.
- **Reuse and new work:**
  - Reuses `VerticalStructure` ×2, `OptionStructureDebit` and the payoff.
  - New: a roll-date gate and a two-vertical composition component.
- **UNKNOWN:**
  - Wrong root or settlement type → UNKNOWN, not substitution.
  - Missing delta.
  - Evaluation off the 11:00 ET snapshot → UNKNOWN or disclosed.
  - The allocation stays UNKNOWN.
- **Translating to SPY is prohibited** because the source is exact about SPX, AM settlement and Black deltas.
- **Verdict: RECOMMEND-WITH-EXTENSION.** It needs an Architect review of:
  - (a) an index-underlying instrument kind;
  - (b) option root and settlement-style identity (the canonical identity must not be parsed);
  - (c) whether provider delta is an acceptable faithful translation of "Black delta closest to", or whether a derived Black-delta fact is needed. That fact would need a rate input that ASA does not acquire.

  The condor package itself needs no new StructureKind.

### C3: Cboe S&P 500 PutWrite (PUT)

- **Source:** Cboe *PUT Methodology*, https://cdn.cboe.com/api/global/us_indices/governance/PUT_Methodology.pdf. The text of the PDF could not be extracted in this session.
- **Rule summary** (secondary source: https://en.wikipedia.org/wiki/CBOE_S%26P_500_PutWrite_Index): sells "a sequence of one-month, at-the-money, S&P 500 Index puts", collateralised by T-bills.
- **Capabilities and fit:** it has the same SPX gaps as C2, plus a single short leg, which needs a new `StructureKind` (CASH_SECURED_PUT or SINGLE_LEG) in the resolver and assessment.
- **Verdict: RECOMMEND-WITH-EXTENSION, low priority.** The exact strike and pricing clauses must be verified from the PDF before intake.

### Rejected

| Candidate | Source | Why rejected |
|---|---|---|
| tastylive 45-DTE credit spread ("~1/3 width", manage at 50% / 21 DTE, IVR filter) | Scattered secondary pages, e.g. optionalpha.com/videos/tastys-best-practices-iron-condor-automated | "About 1/3 width" and "configurable wing width" are vague. It needs IV Rank, which ASA does not acquire, so it would be permanently UNKNOWN. |
| Option Alpha CORE put credit spread bot (30 DTE, −0.30 Δ, IVR > 20, exit at 50% or 5 DTE) | optionalpha.com/bots/core-put-credit-spread-beginner | Needs IV Rank, which is not acquired. The long-leg rule is not public; the page redirects into the app. |
| Data Driven Options credit put spread | C. Allen, datadrivenoptions.com/…/credit-put-spread/ (undated, "updated late 2025") | The rules conflict: DTE "35–49" vs "ideally 35–45" vs "43–46". Credit is "12–18%" vs "15%". Deltas are "around 20/13". Rolling is discretionary. |
| spintwig short SPX put vertical 45-DTE (s1) | spintwig.com, 2024-08-30 | The s1 entry signal is proprietary and paid. The long-leg rule is not disclosed on the page. |
| Earnings ATM straddle, 3 days before announcement (Gao, Xing & Zhang, JFQA 2018) | doi:10.2139/ssrn.2204549 | The full methodology (maturity choice, delta-neutral weights, filters) was not accessible (403). It needs a STRADDLE StructureKind and exit lifecycle. Revisit later. |
| Cboe Zero-Cost Put Spread Collar (CLLZ) | Cboe CLLZ methodology | Needs a long SPX position plus a 3-leg package whose call strike is solved from premium. That is outside options-first proposal scope. |

## Ranked recommendation

1. **C1: Option Alpha SPY 30-DTE put credit spread (hold to expiration).**
   - The rules are explicit and dated. It uses only acquired capabilities and demands that are already shared.
   - It is an exact VERTICAL fit using the existing `VerticalStructure`.
   - It adds a new opportunity type: scheduled, non-signal premium selling.
   - New work is small: a nearest-DTE expiration selector and two derived facts.
2. **C2: Cboe CNDR iron condor.**
   - It has the most explicit source available (a versioned index methodology) and is a distinct neutral, two-sided premium opportunity.
   - It composes from two existing VERTICALs.
   - Start with an Architect review of the index-underlying, root/settlement and delta-model questions. Implement only after that decision. Never approximate it with SPY.

If the Architect declines C2, proceed with C1 alone. Explicit SPY/single-name sources are scarce. Next, recover the full Gao–Xing–Zhang methodology and assess a STRADDLE extension instead of lowering the explicitness bar.
