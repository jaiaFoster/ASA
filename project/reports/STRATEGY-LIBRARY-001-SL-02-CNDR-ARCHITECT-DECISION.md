# Architect decision: SL-02 candidate C2 (Cboe CNDR v4.1)

ROLE-ARCH, read-only, main@7c9bf49.

## Prerequisite decisions

**(a) Index-underlying kind.** `SecurityAssetType.INDEX` already exists (ARCH-005, `domain/financial.py:29`). However, `InstrumentKind` is EQUITY/OPTION/CASH (`domain/operational.py:35`). Live subjects are hard-built as `EQUITY` (`screening/live_context.py:228`; `market_data/tradier.py:580`). Labelling SPX as EQUITY would be untruthful. The fix needs `InstrumentKind.INDEX` plus a way for asset type to reach normalization. That is an additive **domain public-contract change**, so Founder review is required (ADR-010, last line). SPX would also have to enter `APPROVED_LIVE_UNIVERSE`.

**(b) Root and settlement identity.** `OptionContract` has no root, settlement-style or exercise field. SPX (AM) and SPXW (PM) contracts at the same strike and date would therefore coexist in one chain. Only the OCC string would tell them apart, and ARCH-005 forbids parsing it. `_nearest_delta` (`strategies/stonk_components.py:882`) could then silently pick a PM leg. A provider-side root filter hides the semantics, so it is rejected. The fix is a typed `settlement_style` (and root) on `OptionContract`, set by normalization. That is an identity-bearing **ARCH-005 public-contract change** (type-system bump, new replay vectors), so Founder review is required.

**(c) Delta fidelity.** **Decision: provider delta is NOT a faithful translation.** Tradier/ORATS greeks come from ORATS' own volatility surface, rate and dividend inputs, at `greeks.updated_at`. Cboe specifies Black-formula deltas using its own inputs as of 11:00 ET. At ±0.20/±0.05 with 5-point strikes, these differences can change the selected strike, which breaks exact semantics. Fidelity needs a versioned analytics fact, `black_delta`, computed from 11:00 ET mids. It is non-contract and Architect-owned. Its forward and discount inputs are the problem. If the methodology allows implying them from put-call parity on the same chain, no external rate is needed. **This is unverified**, because the packet does not quote CNDR's input clauses. If an external rate is required, ASA needs a new `MarketCapability` (a domain enum change) from a free Treasury source. That is a contract change, not a money blocker. Collateral stays UNKNOWN.

**(d) Tradier SPX coverage. UNVERIFIED.** The code has nothing index-specific. Expirations use `includeAllRoots=false`. Chains send no root parameter. `root_symbol` is never read. `_is_monthly_expiration` is a date heuristic (Friday, day 15–21), not a root fact. No SPX fixtures or tests exist; `providers/` is synthetic only. Index-option entitlement is also unverified; if it is missing, this becomes a vendor question.

## Classification

| Item | Can be done inside the program without a contract change? | Genuine Founder blocker? |
|---|---|---|
| (a) | No: domain enum plus normalization | No. It is a review floor, not one of the six categories |
| (b) | No: identity-bearing ARCH-005 change | No, same reason |
| (c) | Yes if the forward is implied from parity. Otherwise No (new capability) | No |
| (d) | Evidence gap. It could become a vendor blocker only if paid entitlement is needed | Not now |

None of these is a genuine Founder blocker. CNDR is **not uniquely necessary**, so the sprint rule says to skip it.

## Conclusion

**CNDR: (3) BLOCKED for SL-02. Defer it; do not escalate.** No bounded non-contract extension exists, because both (a) and (b) touch public domain contracts. SPY substitution stays prohibited.

If the Founder later wants CNDR, the smallest Founder decision is to approve **one additive ARCH-005 amendment** containing:
- `InstrumentKind.INDEX`;
- a typed `settlement_style` (AM/PM) and root on `OptionContract`, populated by normalization and never parsed.

Architect-owned follow-ups at that point:
- the `black_delta` fact, after the CNDR input clauses are verified;
- a live Tradier SPX probe for roots, `root_symbol` and entitlement.

## SL-02 closure recommendation

SL-02 must **not** claim its "2–4 option strategies" target with only C1. Recommended path:
1. Document the CNDR deferral with this rationale, and record C3 (PUT) as sharing the same SPX gaps.
2. Run one bounded search for another explicit candidate outside SPX. For example, recover the full Gao–Xing–Zhang methodology. A STRADDLE executable structure would need its own Architect review.
3. If no candidate meets the explicitness bar, SL-02 may close with C1 plus the documented deferral. The closure must be recorded as an **explicit target downgrade**, not a pass, with the shortfall stated so the Founder sees it at program closure. It is not a blocker escalation.

Incidental: Tradier labels ETFs `EQUITY` (low-risk debt).
