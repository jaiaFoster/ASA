# STRATEGY-PRODUCTION-001 SP-00A — exact-main rehydration and ownership map

- **Ticket:** SP-00A (Founder Sprint Delegation, Amendment 013, activation `AMD-013-STRATEGY-PRODUCTION-001-V1`)
- **Basis:** `main` @ `5adc932`. Activation PR #505 was authored and personally merged by `jaiaFoster` (ROLE-FOUNDER).
- **Scope:** read-only mapping. No code changes. Risk: R1 (documentation).

## 1. Rehydration evidence

| Check | Result |
|---|---|
| Sprint `status` / `activation.founder_authorized` on main | `ACTIVE` / `true` (PR #505, Founder-merged 2026-09-27T17:37:41Z) |
| PR #502 artifacts present under `research/sprints/ASA-RES-STRATEGY-QUALIFICATION-002/` | `FINAL-SELECTION.md`, `final-selection.yaml`, `implementation-handoff.yaml` (7 `manifest_translation` blocks), `architecture-handoff.yaml`, `derived-fact-registry.yaml`, `gate-registry.yaml`, `capability-map.yaml`, 15 strategy specifications |
| Selected set in the sprint = selected set in `final-selection.yaml` | 7 of 7 ids identical |
| Strategy-production reference path (ADR-010) | manifest → knowledge mapping → subject-first binding → validated contract → `build_migrated_*` registries → scheduler pairs (reference: `spy_put_credit_spread`) |

## 2. Freeze vs. current code (additive deltas recorded)

| Freeze item | Current code | Additive delta (owner) | Ticket |
|---|---|---|---|
| Three-state semantics | The graph has only boolean `boolean_and`/`boolean_or` (`strategies/core_components.py`). `verdict_classifier` emits PASS/WATCH/FAIL. UNKNOWN exists only *before* the graph, as `UnknownReason` from `prepare` (`strategy_runtime/subject_preparation.py`), and is projected as `EvaluationState.MISSING_DATA`. | New `TriState` type and `asa.core` components `tri_and`, `tri_compare`, `tri_gate` in `strategies/`. A new verdict component preserves a distinct UNKNOWN verdict. Runtime projection maps graph UNKNOWN to `MISSING_DATA` with typed reason codes and never to FAIL. | SP-01E |
| X01 INDEX identity | `InstrumentKind` = EQUITY/OPTION/CASH (`domain/operational.py:35`). `SecurityAssetType.INDEX` exists (`domain/financial.py:32`). Tradier builds every subject as EQUITY (`market_data/tradier.py:580`). | `InstrumentKind.INDEX`. The market-data subject carries an asset type so normalization labels index subjects INDEX. | SP-01A |
| X01 settlement style | `OptionContract` has no root or settlement field. Tradier chains are requested without `root_symbol` (`market_data/tradier.py:291-297`). | Optional `root` + `settlement_style` (AM/PM enum) on `OptionContract`, populated by normalization from the provider `root_symbol` (never from OCC text or strategy id). Both enter natural identity only when present, so existing identities stay unchanged. | SP-01A |
| SOQ | absent | New canonical capability `INDEX_SETTLEMENT_VALUE_V1`. Unavailable settlement values are typed UNKNOWN. | SP-01A |
| P03 straddle | `OptionStructureType.STRADDLE` exists (exactly 2 legs, `domain/financial.py:582`). `OptionStructureIntent` accepts VERTICAL/CALENDAR only (`strategy_runtime/option_structure_resolver.py:57`). | `StructureKind.STRADDLE` and `SINGLE_LEG`. The resolver generalizes to N exact legs with per-kind shape validation. A multi-pair collection is a tuple of pair structures, never a GXZ type. | SP-02A (P01 part: SP-03A) |
| P09 overlay | absent | `UnderlyingExposureLeg` (subject, quantity/notional, `exposure_kind` ∈ {`index_total_return`, `tradable_underlying`}, executability flag) in the trade proposal beside the option legs | SP-06A |
| P10 delta-hedged | absent | Static hedge leg that reuses the `UnderlyingExposureLeg` contract (`tradable_underlying`), with its quantity from `DF-DELTA-NEUTRAL-HEDGE-QUANTITY` | SP-05A |
| P12 cross-sectional | `analytics/cross_sectional_ranking.py` (percentile rank, no quantiles). `strategy_runtime/cross_subject_knowledge.py` (return-family materialization). | `analytics/quantile_assignment.py` (RA-XS-01 policy parameterized) plus a generic cross-subject portfolio composition in `strategy_runtime/`, keyed by manifest declaration, never by strategy id | SP-01E / SP-05A |
| A15 margin/capital | Only terminal payoff and modeled P&L exist (`strategy_runtime/option_payoff.py`, `modeled_pnl.py`). No margin model. | `analytics/margin.py`: versioned formula ids per freeze list. Missing inputs yield UNKNOWN. | SP-03A, SP-04A (equity alpha for Zhan, SPAN-or-UNKNOWN for Heston) |
| Assumption provenance | Adapters append free-text `_ASSUMPTIONS` to `decision.assumptions` (e.g. `strategy_runtime/adapters/put_credit_spread_subject_first.py:73`). The manifest has no assumption field. | `ManifestMetadata` gains `implementation_assumptions` (ids, identity-bearing). Semantics-changing values are `ParameterSpec`s. The generic explanation projection discloses the ids. | SP-01E |

All deltas are additive. None redefines an existing identity for data that lacks the new fields.

## 3. Capability → single owner map

| Capability / fact | Owner (module) | Exists? | Consumers | Ticket |
|---|---|---|---|---|
| INDEX quote (value last disseminated before t) | `market_data/` quote path, `REAL_TIME_QUOTE_V1` with an INDEX subject | quote path exists; INDEX kind is new | PUT, PUTY, SCS, BXM | SP-01A |
| Index option chain with root/settlement | `market_data/tradier.py` normalization → `OptionContract` | chain exists; fields new | PUT, PUTY, SCS, BXM | SP-01A |
| Canonical index symbols and root → settlement table | `market_data/index_instruments.py`. This is the single extension point: a new index (XSP, NDX, RUT, VIX) adds rows here, never a second path (per SP-01A-IR-001). | SPX only | index strategies | SP-01A |
| SOQ settlement value | `market_data/`: `INDEX_SETTLEMENT_VALUE_V1` | new | PUT, PUTY, SCS, BXM (outcomes) | SP-01A |
| Treasury 4w/13w bank-discount; risk-free; dividend yield | `market_data/`: `RATE_OBSERVATION_V1`, a provider-neutral `RateObservation` (series id, tenor, basis, effective date) | new | PUT, PUTY, SCS, Zhan | SP-01B |
| Option trade tape; Cboe VWAP input | `market_data/`: `OPTION_TRADE_TAPE_V1` (`OptionTrade`: identity, price, size, event and observed time, sale condition). VWAP formula owned by `analytics/`. | new | PUT, PUTY, BXM | SP-01C |
| S&P 500 dividend points | `market_data/`: `INDEX_DIVIDEND_POINTS_V1` (not `CORPORATE_ACTIONS_V1`) | new | BXM | SP-01D |
| security_type, shares_outstanding | `market_data/`: `SECURITY_MASTER_V1` (point-in-time `SecurityMasterRecord`) | new | Zhan, Heston | SP-01D |
| DF-OPT-MID | `analytics/option_facts.py` | **duplicate debt exists** (see §5) | all 7 | SP-01E |
| DF-OPT-RELATIVE-SPREAD | the existing `compute_bid_ask_spread_ratio` (`analytics/derived_facts.py`) is the single owner; `option_facts.option_relative_spread` only delegates and types failures as UNKNOWN (corrected in SP-01E per SP-01E-IR-001) | exists | Heston gate, A12 diagnostic | SP-01E |
| DF-OPT-WEIGHTED-SPREAD, DF-OPT-EFFECTIVE-PRICE | `analytics/option_facts.py` (A12, measurement only) | new | all 7 / Heston gate | SP-01E |
| DF-OPT-MONEYNESS-KS/SK | `analytics/option_facts.py` | new | Zhan, SCS | SP-01E |
| DF-OPT-DTE-CALENDAR | the registered `days_to_expiration` 1.0.0 (`analytics/forward_factor.py`) is the single owner; `option_facts.calendar_days_to_expiration` delegates (corrected per SP-01E-IR-001) | exists | all 7 | SP-01E |
| Calendar facts: third-Friday roll, first/last trading day, monthly expiration day, session offset | `analytics/calendar_facts.py`, reusing `market_data/session_calendar.py` holidays | holidays exist; facts new | all 7 | SP-01E |
| DF-STRADDLE-ZERO-DELTA-WEIGHT, DF-STRADDLE-RETURN | `analytics/option_returns.py` | new | GXZ, SCS, Heston | SP-01E |
| DF-ZERO-COST-OPTION-RETURN, DF-DN-CALL-WRITE-RETURN | `analytics/option_returns.py` | new | SCS, Zhan | SP-01E / SP-05C |
| DF-CBOE-TBILL-DAILY-ACCRUAL, DF-CBOE-PUT-CONTRACT-COUNT | `analytics/margin.py` (capital/collateral family) | new | PUT, PUTY | SP-01E / SP-03A |
| DF-XS-QUANTILE-ASSIGNMENT | `analytics/quantile_assignment.py` (next to `cross_sectional_ranking.py`) | new | Zhan, Heston | SP-01E |
| DF-DELTA-NEUTRAL-HEDGE-QUANTITY | `analytics/option_facts.py` | new | Zhan | SP-01E |
| A08 point-in-time option panel | `market_data/`: `HISTORICAL_OPTION_PANEL_V1`, read from ASA's own persisted chain observations (no synthetic backfill) | new | Heston | SP-05B |
| A17 straddle-return history | `analytics/option_returns.py` over the A08 panel | new | Heston | SP-05B |
| TriState graph semantics | `strategies/core_components.py` + `strategies/type_system.py` | new | all 7 | SP-01E |
| P01 / P03 / P09 / P10 exact positions | `strategy_runtime/option_structure_resolver.py`, `executable_structures.py`, `trade_proposal.py` | 2-leg only | as §2 | SP-02A, SP-03A, SP-05A, SP-06A |
| P12 cross-sectional portfolio | `strategy_runtime/` generic cross-subject composition | family exists (returns) | Zhan, Heston | SP-05A |
| Registry / scheduler / API / UI / tracking | `strategy_runtime/adapters/__init__.py`, `asa/scheduled_screening.py` pair declarations, generic API/UI projection | exists | all 7 | per strategy, SP-07A |

## 4. Per-strategy mapping

| Strategy | Structure | Canonical inputs | Derived facts | Missing reusable owners | RAs/IAs | Stream |
|---|---|---|---|---|---|---|
| `event_vol_gxz_preea_straddle_to_expiry` | P03 long, multi-pair, zero-delta ratio | equity quote, option chain, earnings calendar, trading calendar | MID, DTE, SESSION-OFFSET, ZERO-DELTA-WEIGHT, STRADDLE-RETURN | P03, TriState | RA-EV-01, RA-EV-02 | A |
| `index_putwrite_cboe_put` | P01 short put | INDEX quote, SPX chain (root/AM), SOQ, T-bill 4w/13w, trade tape | THIRD-FRIDAY-ROLL, MID, TBILL-ACCRUAL, PUT-CONTRACT-COUNT | X01, X04, X05, P01, A15 | IA-PUT-01 | B |
| `index_putwrite_cboe_puty` | P01 short put, 2% OTM | as PUT | as PUT | none beyond PUT (reuse proof) | IA-PUT-01 | B |
| `index_short_vol_scs_near_atm_straddle` | P03 short | INDEX quote, SPX chain, rates, dividend yield | MID, MONEYNESS, DTE, ZERO-COST-RETURN | X01, X04, P03 short, A15 Cboe naked/straddle margin | RA-SV-01 | A |
| `xs_option_zhan_neg_lnprice_dn_call` | P10 inside P12 | equity quotes, chains, security master, rates | MID, MONEYNESS, HEDGE-QTY, QUANTILE, DN-CALL-WRITE-RETURN | security master, P10, P12, A15 equity margin | RA-XS-01 | C |
| `xs_option_heston_straddle_momentum_lowcost` | P03 inside P12 | chains, 12-month panel, security master | MID, WEIGHTED-SPREAD, RELATIVE-SPREAD, STRADDLE-RETURN, QUANTILE | A08, A17, P12, A15 SPAN-or-UNKNOWN | RA-XS-01, RA-XR-03 | C |
| `index_buywrite_cboe_bxm` | P09 index exposure + short SPX call | INDEX quote, SPX chain, SOQ, dividend points, trade tape | THIRD-FRIDAY-ROLL, MID | X01, X05, X07, P09 | none | D |

Every row has exactly one owner per missing capability. No strategy-specific module sits outside `strategies/` (manifest, planning, knowledge) and one subject-first binding per strategy under `strategy_runtime/adapters/`, following the reference pattern.

## 5. Duplicate-owner findings

1. **Option midpoint** is computed in six places:
   - `strategy_runtime/executable_structures.py:61`
   - `strategy_runtime/option_structure_resolver.py:112`
   - `strategy_runtime/forward_outcome.py:220`
   - three adapters' `_spot`
   - `screening/live_adapters.py:304`

   New work uses `DF-OPT-MID` only. Existing sites are pre-existing debt (ADR-010 consequences). They are not rewritten by this sprint unless a ticket touches them. That avoids widening scope.
2. **`OptionContract.mark`** holds provider last trade. It is never used as a midpoint or a Cboe VWAP. This is enforced by X05 acceptance and SP-01E tests.
3. **Correction (SP-01E review SP-01E-IR-001).** `DF-OPT-RELATIVE-SPREAD` is the same formula as the existing `compute_bid_ask_spread_ratio`, and `DF-OPT-DTE-CALENDAR` is the registered `days_to_expiration` feature. Neither gets a second owner: the SP-01E wrappers delegate to the existing functions. No other planned owner duplicates an existing formula.

## 6. Review floor per ticket (RISK-001 §10.1 is unchanged by Amendment 013)

- **R3 (independent review and Architect approval recorded on the PR before delegated merge):**
  - SP-01A (domain identity), SP-01B–D (new canonical capabilities).
  - SP-01E (graph type system), SP-02A, SP-03A, SP-05A, SP-06A (structure contracts).
  - SP-05B (panel contract), SP-07A.
- **R2 (reviewer-asserted, tests as evidence):**
  - strategy tickets SP-02B, SP-03B, SP-03C, SP-04B, SP-05C, SP-05D, SP-06B;
  - SP-04A (formula additions within the SP-03A contract);
  - SP-07B.
- **R1:** SP-00A, SP-00B.
- **Founder-only:** SP-08A deployment.

## 7. Acceptance

- `every_selected_strategy_mapped`: §4, 7/7.
- `every_gap_has_one_owner`: §3.
- `no_duplicate_owner_planned`: §5.
- `architecture_freeze_matches_current_code_or_specific_additive_delta_recorded`: §2.
