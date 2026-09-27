# ASA-RES-STRATEGY-QUALIFICATION-002 — Final strategy selection and implementation handoff

- **Closeout assignment:** ASA-RES-STRATEGY-QUALIFICATION-002-CLOSEOUT (ROLE-RESEARCH, bounded research-selection delegation from the Founder).
- **Basis:** `main` @ 6a8698e (PR #501 merged), plus the ROLE-ARCH review on PR #501.
- **Status:** selection **frozen**.
  - "Selected for implementation handoff" is **not** implementation authorization.
  - The Founder retains authorization to implement, architecture and public-contract acceptance, deployment, capital and live-broker decisions, and governance.

Machine-readable companions:
- [`final-selection.yaml`](final-selection.yaml)
- [`implementation-handoff.yaml`](implementation-handoff.yaml): frozen specifications and manifest translations
- [`architecture-handoff.yaml`](architecture-handoff.yaml)

## 1. Final selected set by lane (7 strategies)

| Lane | Selected strategy (final id) | Research spec | Structure | Qualification | Architecture status |
|---|---|---|---|---|---|
| 1 Event volatility | `event_vol_gxz_preea_straddle_to_expiry`: delta-neutral ATM straddle bought 3 sessions before earnings, held to an expiry 4–10 calendar days away | [EV-01](strategy-specifications/ASA-QS-EV-01-GXZ-PREEA-STRADDLE-TO-EXPIRY.md) | P03 long | READY_WITH_EXPLICIT_UNKNOWNS | P03 multi-pair semantics |
| 2 Index put writing | `index_putwrite_cboe_put`: Cboe PUT, monthly ATM SPX put, T-bill collateralized | [PW-01](strategy-specifications/ASA-QS-PW-01-CBOE-PUT.md) | P01 short | READY_WITH_EXPLICIT_UNKNOWNS | shared primitives only |
| 2 Index put writing | `index_putwrite_cboe_puty`: Cboe PUTY, monthly 2% OTM SPX put | [PW-A1](strategy-specifications/ASA-QS-PW-A1-CBOE-PUTY.md) | P01 short | READY_WITH_EXPLICIT_UNKNOWNS | shared primitives only |
| 3 Index short volatility | `index_short_vol_scs_near_atm_straddle`: Santa-Clara-Saretto monthly short ATM SPX straddle, about 45 days | [SV-01](strategy-specifications/ASA-QS-SV-01-SCS-SHORT-NEAR-ATM-STRADDLE.md) | P03 short | READY_WITH_EXPLICIT_UNKNOWNS | A15 straddle margin |
| 4 Covered call | `index_buywrite_cboe_bxm`: Cboe BXM, S&P 500 index plus monthly ATM call | [CC-01](strategy-specifications/ASA-QS-CC-01-CBOE-BXM.md) | P09 | READY_WITH_EXPLICIT_UNKNOWNS | **ARCHITECT_REVIEW_REQUIRED (P09)** |
| 5 Option-implied information | — (lane closed with zero) | — | — | — | — |
| 6 Cross-sectional option returns | `xs_option_zhan_neg_lnprice_dn_call`: delta-neutral call writing, decile sort on −ln(price), dividend payers included | [XR-01](strategy-specifications/ASA-QS-XR-01-ZHAN-NEG-LNPRICE-DN-CALL.md) | P10 in P12 | READY_WITH_EXPLICIT_UNKNOWNS | P10, P12 |
| 6 Cross-sectional option returns | `xs_option_heston_straddle_momentum_lowcost`: straddle momentum, lags 2–12, low-cost decile variant | [XR-02](strategy-specifications/ASA-QS-XR-02-HESTON-STRADDLE-MOMENTUM.md) | P03 in P12 | READY_WITH_EXPLICIT_UNKNOWNS | P12, A08/A17 |

No selected strategy is IMPLEMENTATION_READY_RESEARCH, because each still depends on canonical inputs or primitive semantics that ASA does not yet have. The Architect agreed this is correct (PR #501 review item 9).

For every selected strategy, the financial specification is complete. There is no trading decision left for implementation to invent. Every remaining item is typed RESEARCH, DATA, ARCHITECTURE or PROVIDER.

## 2. Lanes with fewer than two, and why

| Lane | Selected | Why not two |
|---|---|---|
| 1 | 1 | ALX (concavity) has a look-ahead universe and no source-authored trade direction. Selecting it would require inventing both. The GXZ [−3,0] round trip is net-negative and was not resurrected. |
| 3 | 1 | The targeted pass found one explicit, peer-reviewed, cost-evaluated SPX short-straddle rule (Santa-Clara-Saretto). Its strangle and far-maturity siblings are strike or maturity variants (diversity rule). Bakshi-Kapadia is a measurement design. |
| 4 | 1 | BXMD's Black-delta inputs are still undefined (factsheet and BXRT/BXMVM checked). That is a financial rule, not an Architect-resolvable analytic. BXY is a trivial moneyness variant under the lane-4 rule. |
| 5 | 0 | MPP: skew, IV spread and O/S are insignificant net of borrow fees. The existing evidence base holds no other signal with more than abstract-level evidence. |

## 3. Changes made by the closeout

### Targeted blocker pass

| Blocker | Attempt | Outcome |
|---|---|---|
| GXZ published methodology | Cambridge PDF, Rice copy, SSRN delivery | Not recoverable. The preprint's own text resolves the leg ratio (delta-neutral) and the DTE unit (calendar days, no 10–60 filter for Table 6). Multi-pair volume is a bounded research assumption (RA-EV-01). → **selected** |
| Cboe WPUT timing | One-Week PutWrite methodology (access denied), web sources | Unresolved; the same wording repeats → not selected |
| Cboe BXMD Black inputs | BXMD factsheet, BXRT, BXMVM | Unresolved → not selected |
| Zhan appendix / replication | RFS and SSRN searches | None found. Footnote 8's dividend-inclusive variant removes the look-ahead filter; moneyness is a three-state gate → **selected** |
| Heston appendix / replacement order | JF page, co-author site | None found. The low-cost decile variant is frozen with RA-XR-03 (no replacement) → **selected** |
| SPX short straddle/strangle | Santa-Clara-Saretto full text (already an evidence-base source) | Explicit rule with cost and margin evaluation → **selected** (new spec SV-01) |
| (PUTY evidence) | Cboe PUTY factsheet | Exact-rule statistics recovered → **promoted and selected** |

### PR #501 Architect corrections applied

- **X02a restored** to "live intraday index-option chain acquisition after X01". No selected strategy needs it.
- The SPX reference level is an **INDEX quote** via X01 plus the provider-neutral quote path.
- **Gaps reclassified:**
  - GAP-OPTION-TRADE-PRINTS → **X05** OPTION_TRADE_TAPE
  - GAP-QUOTE-EVENT-CAPTURE → **X06** QUOTE_EVENT_CAPTURE
  - GAP-INDEX-DIVIDEND-POINTS → **X07** INDEX_DIVIDEND_POINTS
  - security type and shares outstanding → **security-master facts**
  - factor data → **research-only**
- PUT and BXM capability mappings corrected.
- BXM architecture status set to ARCHITECT_REVIEW_REQUIRED (P09).
- All prior evidence and qualification history is preserved:
  - appended closeout sections in the specs;
  - `qualification_history` in the matrix;
  - `gap_reclassification_pr501_architect` in the capability map.

## 4. Research assumptions (Researcher decisions, separated from sourced rules)

| ID | Strategy | Assumption | Why it is not an invented trading rule |
|---|---|---|---|
| RA-EV-01 | GXZ | Pair volume = call + put volume at the day −3 close | The source specifies volume weighting. Formation-day volume is the only look-ahead-free choice. The source reports equal, volume and OI weighting as "very similar". |
| RA-EV-02 | GXZ | Expiration dates used as listed; weeklies not excluded | This is the literal source filter. The era difference is recorded as an evidence-transfer uncertainty. |
| RA-SV-01 | SCS | Standard monthly SPX expirations only | Reproduces the instrument set of the 1996–2002 sample. |
| RA-XS-01 | Zhan, Heston | Equal-count quantile mapping; ties share the lowest rank; full-universe breakpoints | Sources say only "sort into deciles". Only boundary stocks are affected. |
| RA-XR-03 | Heston | No replacement in the low-cost variant | Any pair that fails the 50% weighted-spread test also fails the per-leg 10% test. The replacement order is unstated. |

Implementation assumption IA-PUT-01: any rounding of the fractional index contract count is a disclosed implementation choice.

## 5. Shared capabilities to build first

See architecture-handoff.yaml for the full consumer map.

1. **Derived and calendar facts** (all 7): DF-OPT-MID, roll/first/last/expiration-day facts, DF-TRADING-SESSION-OFFSET, DF-STRADDLE-ZERO-DELTA-WEIGHT, DF-STRADDLE-RETURN, DF-ZERO-COST-OPTION-RETURN, DF-CBOE-TBILL-DAILY-ACCRUAL.
   - `OptionContract.mark` is the provider last trade and must not stand in for the midpoint.
2. **X01 + INDEX quote + SOQ** (PUT, PUTY, SCS, BXM), with **X04** rates (PUT, PUTY, SCS, Zhan).
3. **A15** collateral and margin (PUT, PUTY, SCS, Zhan, Heston).
4. **P03** straddle, including short, non-unit ratios and multi-pair (GXZ, SCS, Heston). **P01** (PUT, PUTY).
5. **Security-master facts**, **P10**, **P12** (Zhan, Heston). **A08/A17** (Heston).
6. **X05** option trade tape (PUT, PUTY, BXM outcome valuation). **X07** and the **P09 Architect resolution** (BXM).

## 6. Remaining unknowns that are provider/data questions, not financial rules

| Item | Type | Strategies |
|---|---|---|
| Option trade prints for Cboe VWAP entry (X05) | DATA | PUT, PUTY, BXM (outcome valuation only) |
| SOQ settlement value; INDEX quotes (X01) | DATA | PUT, PUTY, SCS, BXM |
| Treasury bank-discount rates; risk-free rate and dividend yield (X04) | DATA | PUT, PUTY, SCS, Zhan |
| S&P 500 dividend points (X07) | DATA | BXM |
| security_type, shares_outstanding | DATA | Zhan, Heston |
| 12-month historical option panel (A08) | DATA | Heston |
| Provider delta vs OptionMetrics or Black-Scholes delta | PROVIDER | GXZ, Zhan, Heston (Zhan footnote 12 bounds the materiality) |
| Account capital allocated to each strategy | Founder capital decision (retained) | all |

## 7. Recommended dependency-aware implementation order

This is an engineering sequence to minimize duplicate work, not a product-priority ranking.

| Step | Build | Proves |
|---|---|---|
| 1 | Shared derived and calendar facts; A12 diagnostics | fact library for all 7 |
| 2 | P03 (long, non-unit ratio, multi-pair) | **GXZ** (lane-1 reference). Needs no index work, so it can start first. |
| 3 | X01 + INDEX quote + SOQ, X04, P01, A15 T-bill collateral | **PUT** (lane-2 reference), then **PUTY** (reuse proof: no new primitive) |
| 4 | P03 short + A15 CBOE index margin | **SCS** (lane-3 reference; reuses X01, X04, P03) |
| 5 | security-master facts, P10, P12, A15 equity margin | **Zhan** (lane-6 reference) |
| 6 | A08, A17 | **Heston** (lane-6 second; reuse proof for P03 + P12) |
| 7 | P09 Architect resolution, X07; X05 in parallel from step 3 | **BXM** (lane-4; architecture-gated) |
