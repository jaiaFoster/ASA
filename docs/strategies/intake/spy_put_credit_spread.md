# Intake: `spy_put_credit_spread` (SL-02)

## 1. Source

- Option Alpha, "8 SPY Put Credit Spread Backtest Results Analyzed" — Kirk Du
  Plessis, Steve Henry, Ryan Hysmith; published 2021-11-17, updated
  2023-01-11. https://optionalpha.com/blog/spy-put-credit-spread-backtest
- Scope: **backtest 1 only**. Verified verbatim on 2026-09-24: SPY;
  "30 days to expiration"; "0.30 delta for the short contract and 0.10 delta
  for the long contract"; "No profit targets or stop-loss levels"; "Hold the
  position to expiration"; "Only one position active at any time".
- Why: explicit, dated source; options-first; only acquired capabilities
  (SPY chains already shared with Forward Factor and Skew Momentum); exact
  VERTICAL fit; a new opportunity type (scheduled premium selling) distinct
  from event, term-structure, and directional-debit strategies; no paid data.
- Ambiguities and resolutions:
  - "30 days" → the future expiration nearest 30 calendar DTE. An
    equidistant tie is `ambiguous_expiration_tie` (never a chosen side).
  - Delta → provider-observed delta, nearest absolute value; a missing delta
    is `missing_actual_delta` (never a proxy).
  - Variants 2–4 (targets/stops/15 DTE/rolling) are excluded: their bases are
    undefined in the source.
  - ASA constructibility tolerances (not source rules; disclosed as proposal
    assumptions): each leg's observed delta within ±0.05 of its source
    target, and the expiration within ±7 days of 30 DTE. An exact delta tie
    is `ambiguous_delta_tie`. The graph is the single leg-selection
    authority; the trade card resolves exactly the graph's contracts.
  - "One position active" is portfolio state, not screener semantics; every
    result carries the disclosure warning
    `source_one_active_position_rule_not_evaluated_by_screener`.

## 2. Strategy semantics

| Item | Source rule | ASA representation |
|---|---|---|
| Entry gates | none | graph constant PASS once evaluable |
| Exit / lifecycle | hold to expiration | no management; terminal payoff |
| Structure | bull put spread | `StructureKind.VERTICAL` |
| Expiration | 30 DTE | nearest 30 calendar DTE (planning) |
| Strikes | short 0.30Δ, long 0.10Δ puts | `vertical_structure` long −0.10 / short −0.30 |
| Liquidity | none stated | diagnostics only (no invented gate) |
| Exclusions | none | none |
| Allocation | not defined | none |

## 3. Manifest

- [x] `spy_put_credit_spread@1.0.0`, schema 1.1.0; capabilities
      `real_time_quote_v1`, `option_chain_v1`.
- [x] Graph: `asa.stonk.options/vertical_structure` → `option_structure_debit`;
      `asa.core/constant` → `asa.stonk.shared/verdict_classifier`. No new
      component.
- [x] Outputs: `structure` (structure), `mid_debit`/`conservative_debit`
      (fact), `verdict` (verdict).

## 4. Data and analytics

- [x] No new derived fact: max loss/profit/breakeven come from the existing
      deterministic terminal payoff over the exact legs.
- [x] Capabilities overlap fully with current acquisition. Paid data: no.

## 5. Runtime

- [x] Graph-only adapter; contract validated by `validate_manifest_contract`;
      real catalog `manifest_id`.
- [x] Subject-first binding through the shared market-data authority; no
      strategy-ID branch in `screening/` or `strategy_runtime/`.
- [x] Scheduled via `FIXED_SUBJECT_OPTION_UNIVERSE` (SPY) on its own isolated
      invocation; API active scope from `SCHEDULED_FIXED_SUBJECT_PAIRS`.

## 6. UNKNOWN behavior

| Missing input | Typed reason |
|---|---|
| no future expiration | `no_future_expiration` |
| equidistant expirations | `ambiguous_expiration_tie` |
| no puts at expiration | `no_put_contracts_at_selected_expiration` |
| < 2 puts with observed delta | `missing_actual_delta` |
| unusable quote / chain | `unusable_quote` / `unusable_option_chain` |
| expiration > 7 days from 30 DTE | `no_expiration_near_target` |
| leg delta > 0.05 from target | `no_contract_near_target_delta` |
| equal-distance delta candidates | `ambiguous_delta_tie` |
| short strike not above long strike | `inverted_spread` |
| modeled entry not a credit | `non_credit_entry` |
| leg not resolvable | resolver typed blocker (e.g. `no_compatible_contract`) |

## 7. User presentation

Exact two-leg trade card (sell 0.30Δ put, buy 0.10Δ put), modeled credit,
deterministic max loss / max profit / breakeven, payoff diagram, Track This.

## 8. Proof

- [x] Replay determinism, complete projection, typed-failure tests
      (`tests/strategy_runtime/adapters/test_put_credit_spread_subject_first.py`).
- [ ] Observation: OP-07 collector / funnel census after deploy (SL-05).

## 9. Attestation

- [x] No ADR-010 deviation.
