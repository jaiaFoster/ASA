# SL-02 second-candidate search (read-only, 2026-09-24)

Scope: I made about 11 web lookups for up to 3 candidates. None of them fits a plain VERTICAL or CALENDAR, so there is **no no-extension candidate**. One candidate meets the explicitness bar, and it needs an extension.

## Candidate A: Gao/Xing/Zhang pre-earnings ATM straddle, window [-3, 0]

**Sources**
- Preprint: Xing & Zhang, "Anticipating Uncertainty: Straddles Around Earnings Announcements", SSRN 2204549, dated **January 14, 2013**. The full text is accessible via Quantpedia: https://quantpedia.com/www/Anticipating_Uncertainty-Straddles_Around_Earnings_Announcements.pdf
- Published version: Gao, Xing & Zhang, JFQA 53(6):2587-2617, Dec 2018. https://doi.org/10.1017/S0022109018000285. The full text was not accessible (the Cambridge page returned the abstract only, and the Rice preprint URL returned 403).

**Verbatim rules (2013 preprint)**
- Universe and filters:
  - "We only include options with 10 to 60 days to maturity on common stocks with prices of at least $5."
  - "We take the mid-quote value as a fair reflection of the option price and require it to be at least $0.125."
  - "we require bid and ask price to satisfy basic arbitrage bounds". Footnote 5 defines this as "bid>0, bid<offer; for put options we require strike >= bid and offer >= max(0, strike price-stock price); for call option we require stock price >=bid and offer >= max(0, stock price-strike price)".
- ATM selection:
  - "At the time of the straddle formation, we include only options with an absolute delta between 0.375 and 0.625 … and with positive open interest."
  - "We require options to have moneyness [stock price over strike price] between 0.95 and 1.05 to be at-the-money."
- Structure:
  - "For the simple straddle, the investor purchases a pair of call and put options with matching strike prices and maturity dates."
  - Delta-neutral variant: "the weights are adjusted to make the straddle delta to be zero."
  - "Whenever there is more than one pair … on the same stock on the same day, we either equal weight or volume weight individual straddles."
  - "Results obtained using simple straddles and delta-neutral straddles are quantitatively very similar". Simple [-3,0] is tabulated separately.
- Timing: "we long straddles 3 days before the earning announcement and sell them at the close on earnings announcement days, which results in a 3-day holding period."
- Evidence:
  - In the preprint, [-3,0] equal-weighted return is 3.00%, with t > 15.
  - The published abstract reports 3.34% for [-3,0].

**Capability fit**
- Every input is acquired:
  - earnings date: `EARNINGS_CALENDAR_V1`;
  - trading-day offset: session calendar;
  - stock price: quote or bar;
  - chain with provider delta, bid/ask, OI, expirations.
- It needs no IV Rank, rates, or index underlying.
- The universe is S&P 500 single names.

**Structure fit: not a VERTICAL or CALENDAR, and it cannot be composed from them.** It needs STRADDLE (same strike and expiry, long call plus long put) promoted from domain-only `OptionStructureType` to an executable 2-leg `StructureKind`. The resolver's `_shape` must accept it, and the result must not be reported as CUSTOM or `DIFFERENT_STRUCTURE_AVAILABLE`.

**Fidelity issues the Architect must rule on**
1. **Pair multiplicity.** The paper averages over *all* qualifying pairs, weighted equally or by volume. It does not pick one strike or expiry. There are two options:
   - evaluate all qualifying pairs as a set;
   - add a selection rule, which the source does not contain and would be a deviation.

   Picking a pair "nearest ATM" is not in the source.
2. **Weights.** Recommend the *simple* 1:1 straddle, which is explicit and reported. The delta-neutral variant gives no formula, only "adjusted to make … delta … zero", so it would need a derived weight fact.
3. **Timing.** The paper uses closing mid-quotes on day -3 and the EA-day close. ASA snapshots are not at the close, so this must be disclosed or produce UNKNOWN.
   - The AMC/BMO timing of the announcement matters: a BMO event has already happened by the EA-day close.
   - The earnings calendar's hour field must be readable; if it is not, the result is UNKNOWN.
4. **Version.** The published 2018 methodology may differ from the 2013 preprint: the sample was extended and the headline figures changed. It must be verified before intake, or the preprint must be pinned explicitly as the cited version.

**Differentiation.** It is long realized-move and gamma, with a pre-event exit. The existing earnings calendar is short front-month event IV and held through the crush. This is meaningfully different in direction of vol exposure and in lifecycle.

**Verdict: RECOMMEND-WITH-EXTENSION.** It is the only candidate that clears the explicitness bar. It needs an Architect review of the STRADDLE StructureKind and the pair-multiplicity rule.

## Candidate B: SPY/QQQ bear call (call credit) spread with explicit rules

**Lookups**
- https://optionalpha.com/strategies/bear-call-credit-spread is an educational guide, not a dated backtest methodology.
- The Option Alpha backtest (https://optionalpha.com/blog/spy-put-credit-spread-backtest, 2021-11-17, updated 2023-01-11) covers put spreads only.
- Generic pages quote "30–45 DTE, 16–20 delta" as ranges without a source, for example https://apexvol.com/strategies/credit-spread. That fails the explicitness bar.
- spintwig reports that 45-DTE short SPX calls "have generally experienced a negative expected value" (https://spintwig.com/short-spx-call-45-dte-s1-signal-options-backtest/). That test is SPX, uses the proprietary s1 signal, and returned 403 to fetch.

**Capability and structure fit.** The fit would be fine: a VERTICAL of calls, with every input acquired.

**Differentiation.** A mirror of C1 is the same opportunity type: scheduled, unconditional premium selling on an index ETF. Flipping the side changes the directional sign, not the opportunity. It is borderline-cosmetic.

**Verdict: REJECT.** No explicit, dated, citable rule set was found, and it is weakly differentiated from C1.

## Candidate C: IWM/QQQ 45-DTE 16-delta put credit spread

**Lookups.** The spintwig IWM and NDX 45-DTE tests (https://spintwig.com/short-iwm-put-45-dte-s4-signal-options-backtest/, data to 2024-09-30; https://spintwig.com/qqq-short-put-45-dte-leveraged-options-backtest/) have these problems:
- They are *single short puts*, not verticals.
- They are gated by proprietary paid signals (s4/s5).
- NDX is an index underlying.
- The pages return 403.

No dated, explicit, non-signal IWM or QQQ put-vertical methodology was found. The tastylive 45-DTE/16-delta rules remain scattered and IVR-gated, as the prior packet already rejected.

**Differentiation ruling.** Changing the underlying (SPY to IWM or QQQ), the delta (0.30/0.10 to 0.16/x) and the DTE (30 to 45) while keeping an unconditional, scheduled, short put vertical is a **cosmetic variant** of C1. It is the same opportunity type (index-ETF put-side VRP harvest) with the same structure and lifecycle. Under the SL rules that does not count.

**Verdict: REJECT.** It is a cosmetic variant, and no explicit source was found.

## Idea 4: post- or pre-earnings verticals (PEAD etc.)

Only undated blog heuristics were found, such as "entry on day 2-3 after earnings … exits 15-25 days after entry" (https://optionspilot.app/blog/post-earnings-drift-options-trading-strategy). There are no strike or delta rules and no dated methodology. Earnings iron-condor searches returned anecdotes only.

**Verdict: REJECT.** It does not meet the explicitness bar.

## Bottom line

- **No candidate meets the bar without an extension.** The only explicit, dated, differentiated, capability-complete candidate is **A, the Gao/Xing/Zhang pre-earnings straddle**, rated RECOMMEND-WITH-EXTENSION.
- If the Architect declines the STRADDLE extension, or declines the all-qualifying-pairs semantics, SL-02 should close with **C1 alone plus a documented target downgrade**. The bar must not be lowered to admit B, C or the PEAD ideas.
