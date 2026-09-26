# RES-001A — Broad Options Strategy Landscape Survey

- **Sprint / ticket:** ASA-RES-SPRINT-001 / RES-001A
- **Researcher:** ROLE-RESEARCH (ASA-Strategy-Researcher-001)
- **Date:** 2026-09-26
- **Status:** complete (breadth sufficient for taxonomy; see §5)

This is a landscape inventory. It does not rank, select, or recommend any family. Inclusion means only that the family is externally documented.

Claim classes follow the library standard: **REPORTED**, **DERIVED**, **INFERENCE**, **UNKNOWN**. Every empirical statement here resolves to a source record in `research/sources/`. Values are in the source records and are not repeated here.

## 1. Discovery method

Discovery did **not** start from ASA's shortlist or its capabilities. Iron condors, diagonals, butterflies, put credit spreads, calendars, and skew verticals were treated as hypotheses inside the landscape.

Discovery ran in five independent passes. Each pass started from a different source class, so that no single vantage point defined the landscape.

| Pass | Starting point | What it contributes |
|---|---|---|
| P1 | Peer-reviewed asset-pricing literature on option returns: index options, the cross-section of equity options, and option-implied signals | The economically grounded premia and anomalies |
| P2 | Exchange benchmark indices (Cboe BXM, PUT, WPUT, PPUT, CNDR, BFLY, collars) | The rule-explicit, predominant institutional strategies |
| P3 | Institutional and practitioner quantitative research (AQR, GSAM, Cboe-commissioned) | Decomposition, implementation, and myth-busting evidence |
| P4 | Industry manager classification (Cboe Eurekahedge volatility indices: short vol, long vol, relative-value vol, tail risk) | Checks for missing practitioner families |
| P5 | Market-structure and investor-outcome literature (retail trading, 0DTE, volatility-ETP failures, trading costs) | Negative findings, failure modes, execution evidence |

Each pass was followed by targeted searches for replications, contradictions, and post-publication evidence. Bibliographic identity was verified through Crossref for every peer-reviewed source. Abstracts came from OpenAlex, Semantic Scholar, or RePEc IDEAS. Each record's `verification_depth` states exactly how far it was checked.

## 2. Coverage record (auditable saturation)

Categories examined, with the families each produced (family IDs are defined in RES-001B):

| # | Category examined | Families surfaced | New families? |
|---|---|---|---|
| 1 | Index option return puzzles (put overpricing, straddle returns, delta-hedged gains) | VRP-INDEX-PUTWRITE, VRP-INDEX-SHORT-VOL, LONGVOL-TAIL-HEDGE | yes (first pass) |
| 2 | Benchmark option-writing indices | VRP-COVERED-CALL, VRP-INDEX-PUTWRITE, VRP-DEFINED-RISK, LONGVOL-COLLAR, VRP-ULTRA-SHORT-DATED (WPUT) | yes |
| 3 | Variance swaps and the variance term structure | VRP-INDEX-SHORT-VOL, TERM-STRUCTURE | TERM-STRUCTURE new |
| 4 | VIX futures and volatility ETPs | VOLDERIV-VIX-CARRY | yes |
| 5 | Cross-section of delta-hedged/straddle equity option returns | XS-OPTION-RETURNS | yes |
| 6 | Option return momentum and seasonality | XS-OPTION-MOMENTUM | yes |
| 7 | Lottery, skewness, embedded leverage | XS-LOTTERY-SKEW-OPTION | yes |
| 8 | Earnings, political, and scheduled events | EVENT-VOL | yes |
| 9 | Option-implied predictors of stock returns (smirk, IV spread, RNS, O/S, put-call ratio, vol-of-vol) | OPTION-SIGNAL-EQUITY | yes |
| 10 | Skew and higher-moment risk premia at index level | SKEW-PREMIUM-INDEX | yes |
| 11 | Correlation / dispersion | DISPERSION-CORRELATION | yes |
| 12 | Parity, box spreads, dividend exercise | ARBITRAGE-PARITY | yes |
| 13 | Non-equity volatility premia (FX, commodity, cross-asset) | CROSS-ASSET-VRP | yes |
| 14 | Retail and discretionary option buying outcomes | DIRECTIONAL-OPTION-EXPRESSION (negative evidence) | yes |
| 15 | 0DTE / weekly options | VRP-ULTRA-SHORT-DATED | reproduced (existing) |
| 16 | Hedge-fund volatility manager classification (Eurekahedge) | short vol, long vol, relative value, tail risk | **none new**: maps to existing families |
| 17 | General "systematic option strategy survey" search | straddles, strangles, calendars, naked/covered writing | **none new** |
| 18 | Dispersion-trading empirical search | DISPERSION-CORRELATION | **none new** |
| 19 | Short-volatility failure (Feb-2018) search | VOLDERIV-VIX-CARRY failure mode | **none new** |
| 20 | Practitioner structure names (iron condor, iron butterfly, jade lizard, broken-wing butterfly, wheel, poor-man's covered call, ratio spreads, risk reversals) | reduce to primitives of existing families (RES-001B §3) | **none new** |

**Saturation conclusion (INFERENCE).** Passes 16–20 were broad searches from new vantage points. They produced no family outside the 19 already identified. They added only failure modes, variants, or further evidence for existing families. Under the sprint's saturation rule, this supports stopping breadth discovery. The claim is not that every named strategy has been enumerated. Named practitioner structures were deliberately collapsed into structural primitives (RES-001B).

## 3. Landscape inventory

Predominance vocabulary:
- **predominant**: exchange benchmark and/or large institutional product usage.
- **established**: repeated peer-reviewed evidence.
- **specialty**: evidence exists but the family needs unusual data, execution, or instruments.
- **niche**: sparse or single-study evidence.

Evidence state vocabulary:
- **abundant**: several independent peer-reviewed sources.
- **moderate**: primary peer-reviewed plus limited follow-up.
- **sparse**: one or two sources, or non-peer-reviewed only.
- **contradictory**: credible sources disagree on sign or significance.
- **absent**: no credible source found.

| Family ID | Common names / members | Economic mechanism (source) | Market view expressed | Predominance | Evidence state | Key sources |
|---|---|---|---|---|---|---|
| FAM-VRP-INDEX-PUTWRITE | cash-secured index put writing (Cboe PUT), OTM put selling | Index puts priced above physical expectation. The cause is disputed: crash-risk compensation vs demand pressure (GARLEANU-PEDERSEN-POTESHMAN-2009, CONSTANTINIDES-JACKWERTH-SAVOV-2013, BONDARENKO-2014) | mildly bullish; short volatility; short crash | predominant | abundant, **contradictory on interpretation** | BONDARENKO-2019-CBOE, UNGAR-MORAN-2009, BROADIE-CHERNOV-JOHANNES-2009, CHAMBERS-ET-AL-2014, SANTACLARA-SARETTO-2009 |
| FAM-VRP-COVERED-CALL | buy-write (BXM), overwriting | Equity premium plus short-volatility premium, plus an uncompensated equity-reversal exposure (ISRAELOV-NIELSEN-2015-FAJ) | bullish with capped upside; short volatility | predominant | abundant | WHALEY-2002, HILL-ET-AL-2006, KAPADIA-SZADO-2007, FIGELMAN-2008, ISRAELOV-NIELSEN-2014 |
| FAM-VRP-INDEX-SHORT-VOL | short straddle/strangle, delta-hedged option writing, short variance | Negative market volatility risk premium (BAKSHI-KAPADIA-2003, CARR-WU-2009) | direction-neutral; short volatility and jumps | established | abundant; significance contested for OTM (BROADIE-CHERNOV-JOHANNES-2009) | COVAL-SHUMWAY-2001, BAKSHI-KAPADIA-2003, CARR-WU-2009, FALLON-PARK-YU-2015, BOLLERSLEV-TAUCHEN-ZHOU-2009 |
| FAM-VRP-DEFINED-RISK | put/call credit spreads, iron condor (CNDR), iron butterfly (BFLY) | The same VRP as above, with tail exposure truncated by long wings (INFERENCE) | range-bound or mildly directional; short volatility; long far tail | predominant (practitioner), benchmarked | **sparse** independent evidence; sponsor-commissioned only | CBOE-CNDR-BFLY-METHODOLOGY, OA-SPY-PCS-2021, CHAPUT-EDERINGTON-2003, VILKOV-0DTE |
| FAM-VRP-ULTRA-SHORT-DATED | 0DTE and weekly premium selling (WPUT), same-day condors/butterflies | Short-horizon VRP and jump premium (ANDERSEN-FUSARI-TODOROV-2017) | intraday/short-horizon short volatility | predominant by volume (retail) | sparse; **negative net-of-cost** after the corrected study | VILKOV-0DTE, BANDI-FUSARI-RENO-0DTE, BONDARENKO-2019-CBOE, BECKMEYER-BRANGER-GAYDA-0DTE |
| FAM-LONGVOL-TAIL-HEDGE | protective puts (PPUT), tail-risk funds, long VIX calls | Buyer pays the insurance premium in exchange for crash convexity | bearish tail / long volatility | established | abundant; **negative on return** | ISRAELOV-2018, ISRAELOV-NIELSEN-2015-JPM, BONDARENKO-2019-CBOE, CHAMBERS-ET-AL-2014, SZADO-2009 |
| FAM-LONGVOL-COLLAR | zero-cost collars, put-spread collars | Gives up equity premium and upside to fund downside protection | bullish with bounded range | established (institutional overlays) | moderate; **contradictory** | ISRAELOV-KLEIN-2016, SZADO-SCHNEEWEIS-2010 |
| FAM-VOLDERIV-VIX-CARRY | short VIX futures roll, inverse VIX ETPs, long VIX ETPs | VIX futures contango reflects a variance premium (JOHNSON-2017) | short or long volatility term premium | specialty | moderate; failure-mode evidence abundant | WHALEY-2013, AUGUSTIN-CHENG-VANDENBERGEN-2021, ALEXANDER-KOROVILAS-KAPRAUN-2016, JOHNSON-2017 |
| FAM-TERM-STRUCTURE | calendar spreads, forward-volatility trades, term-slope straddle sorts | Variance premium concentrated at the short end (DEWBECKER-ET-AL-2017); slope predicts returns (VASQUEZ-2017, JOHNSON-2017) | relative value across expirations | established | moderate | VASQUEZ-2017, JOHNSON-2017, DEWBECKER-ET-AL-2017, EGLOFF-LEIPPOLD-WU-2010 |
| FAM-XS-OPTION-RETURNS | cross-sectional delta-hedged option/straddle portfolios on IV-RV, idiosyncratic vol, illiquidity, order flow, characteristics | Dealer inventory and limits to arbitrage; mispricing vs latent factors disputed | market-neutral relative value in volatility | established (academic) | abundant; **contested alpha** (IPCA) | GOYAL-SARETTO-2009, CAO-HAN-2013, ZHAN-ET-AL-2022, BALI-ET-AL-2023, HORENSTEIN-VASQUEZ-XIAO-2026, GOYAL-SARETTO-2022-IPCA |
| FAM-XS-OPTION-MOMENTUM | straddle-return momentum; quarterly seasonal continuation | Implied variance under-reacts to persistent realized variance patterns | relative value in volatility | established (recent) | moderate; replication by others not found | HESTON-ET-AL-2023, HESTON-ET-AL-2026 |
| FAM-XS-LOTTERY-SKEW-OPTION | selling lottery-like / high-skew / high-embedded-leverage options | Buyers overpay for skewness and leverage; intermediaries earn a premium | short lottery exposure | established (academic) | abundant | BOYER-VORKINK-2014, BYUN-KIM-2016, FRAZZINI-PEDERSEN-2022, BALI-MURRAY-2013, CHOY-2015 |
| FAM-EVENT-VOL | pre-earnings straddles, post-earnings IV crush, event-spanning calendars, political-event options | Anticipated announcement uncertainty is priced (DUBINSKY-ET-AL-2019); investors underestimate or overpay depending on subsample | long or short event volatility | established | moderate; **contradictory on sign** by window and firm type | GAO-XING-ZHANG-2018, BARTH-SO-2014, DUBINSKY-ET-AL-2019, DESILVA-SMITH-SO-2026, KELLY-PASTOR-VERONESI-2016 |
| FAM-OPTION-SIGNAL-EQUITY | smirk, call-put IV spread, IV changes, risk-neutral skewness, O/S, put-call ratio, vol-of-vol | Informed trading in options, and short-sale constraints (borrow fees) | directional equity | established | abundant; **contradictory** (RNS sign) and **decaying** (borrow-fee adjustment) | XING-ZHANG-ZHAO-2010, CREMERS-WEINBAUM-2010, AN-ET-AL-2014, CONRAD-DITTMAR-GHYSELS-2013, STILGER-KOSTAKIS-POON-2017, MURAVYEV-PEARSON-POLLET-2025 |
| FAM-SKEW-PREMIUM-INDEX | risk reversals, skew swaps, put-skew selling | Demand for downside protection steepens the smirk (BOLLEN-WHALEY-2004, GARLEANU-PEDERSEN-POTESHMAN-2009) | short downside skew | specialty | moderate; **negative for standalone skew** (KOZHAN-NEUBERGER-SCHNEIDER-2013) | KOZHAN-NEUBERGER-SCHNEIDER-2013, BOLLEN-WHALEY-2004, BAKSHI-KAPADIA-MADAN-2003 |
| FAM-DISPERSION-CORRELATION | short index vol / long constituent vol, correlation swaps | Priced correlation risk | short implied correlation | specialty (institutional) | moderate; **not exploitable with frictions** (source's own finding) | DRIESSEN-MAENHOUT-VILKOV-2009, MARSHALL-2009, FARIA-KOSOWSKI-WANG-2022 |
| FAM-ARBITRAGE-PARITY | box spreads, dividend-exercise plays, parity violations | Financing convenience yields; exercise frictions; short-sale constraints | rate / arbitrage; no volatility or direction view | niche | sparse (in this sprint) | VANBINSBERGEN-DIAMOND-GROTTERIA-2022, POOL-STOLL-WHALEY-2008, OFEK-RICHARDSON-WHITELAW-2004 |
| FAM-CROSS-ASSET-VRP | FX, commodity, rates option writing | Same insurance-selling premium outside equities | short volatility (non-equity) | established (institutional) | moderate | LOW-ZHANG-2005, FALLON-PARK-YU-2015, TROLLE-SCHWARTZ-2010, ILMANEN-2012 |
| FAM-DIRECTIONAL-OPTION-EXPRESSION | long calls/puts, debit verticals, LEAPS stock replacement, discretionary retail buying | Buying options expresses a view but pays the embedded leverage/VRP premium | directional, long convexity | predominant (retail volume) | abundant; **negative** for systematic buyers | BAUER-COSEMANS-EICHHOLTZ-2009, BRYZGALOVA-ET-AL-2023, FRAZZINI-PEDERSEN-2022, COVAL-SHUMWAY-2001, HU-JACOBS-2020 |

Existing library records map into this landscape as follows. They are reused, not duplicated.

- `ASA-RSCH-SPY-PCS-001` is one rule-explicit instance of FAM-VRP-DEFINED-RISK.
- `ASA-RSCH-SKEW-MOMENTUM-001` is a hybrid. Its signal belongs to FAM-OPTION-SIGNAL-EQUITY (with IV-RV components from FAM-XS-OPTION-RETURNS). Its expression belongs to FAM-DIRECTIONAL-OPTION-EXPRESSION (a defined-risk vertical).
- `ASA-RSCH-TGSM-001` is an equity sector-rotation strategy. It is outside the options landscape and is unaffected by this sprint.

## 4. What a capability-first discovery would have missed (INFERENCE)

ASA's current structures are vertical, calendar, and double calendar. Its data are a single-name/ETF chain snapshot, quotes, underlying bars, and earnings dates. Starting discovery from those capabilities would likely have missed:

1. **The whole cross-sectional option-return literature** (FAM-XS-OPTION-RETURNS, -MOMENTUM, -LOTTERY-SKEW). It is the most heavily peer-reviewed part of the landscape. It needs delta-hedged or straddle positions across many underlyings and historical option panels.
2. **Delta-hedged volatility trading.** Much of the primary evidence for the VRP is on delta-hedged positions, not on the unhedged verticals ASA can already express.
3. **Index (SPX) products.** The predominant benchmarks (PUT, BXM, CNDR, BFLY, WPUT) are defined on SPX. ASA's prior Architect decision found SPX blocked by instrument-kind and settlement-root gaps (`project/reports/STRATEGY-LIBRARY-001-SL-02-CNDR-ARCHITECT-DECISION.md`).
4. **Correlation/dispersion and cross-asset VRP**, which need multi-underlying or non-equity instruments.
5. **Negative-evidence families** (long options, tail hedging, 0DTE). The relevant evidence is about why they lose, and that evidence informs the risk dimensions of every other family.

## 5. Evidence gaps and negative findings (preserved)

**Negative or contradictory findings recorded as outcomes:**

- 0DTE: the only systematic multi-strategy study (VILKOV-0DTE) issued an erratum. After correction, *no strategy or basket retains a positive net Sharpe ratio*. Pre-erratum figures are superseded.
- Put writing: the premium is statistically fragile under model-based inference (BROADIE-CHERNOV-JOHANNES-2009). It is rejected as model-consistent on a longer sample (CHAMBERS-ET-AL-2014). It is explained by crisis factors (CONSTANTINIDES-JACKWERTH-SAVOV-2013). Margin frictions materially cut the realizable returns (SANTACLARA-SARETTO-2009). Since weekly launch (2006–2018), PUT's Sharpe ratio was 0.50, below the S&P 500's 0.51 (BONDARENKO-2019-CBOE). That is post-publication evidence of a weaker premium.
- Correlation premium: the source itself reports it cannot be exploited with realistic frictions (DRIESSEN-MAENHOUT-VILKOV-2009).
- Standalone skew premium: it is insignificant once variance exposure is hedged (KOZHAN-NEUBERGER-SCHNEIDER-2013).
- Option-implied equity signals: about two-thirds of the predictability disappears after the borrow-fee adjustment (MURAVYEV-PEARSON-POLLET-2025). Put-call parity predictability declined within its own sample (CREMERS-WEINBAUM-2010). The sign of risk-neutral skewness conflicts across studies (CONRAD-DITTMAR-GHYSELS-2013 vs STILGER-KOSTAKIS-POON-2017).
- Cross-sectional option alpha: 50–75% of it is explained by IPCA latent factors (GOYAL-SARETTO-2022-IPCA). A four-factor model spans much of it (HORENSTEIN-VASQUEZ-XIAO-2026).
- Tail hedging and collars: the evidence is negative on expected return (ISRAELOV-2018, ISRAELOV-KLEIN-2016, ISRAELOV-NIELSEN-2015-JPM). The Tail Risk hedge-fund index had a negative Sharpe (EUREKAHEDGE-CBOE-VOL-INDICES).
- Long VIX ETPs lose over time (WHALEY-2013). Their diversification benefit is almost never realized (ALEXANDER-KOROVILAS-KAPRAUN-2016). Short-vol ETPs failed catastrophically on 2018-02-05 (AUGUSTIN-CHENG-VANDENBERGEN-2021).
- Retail and discretionary option buying loses on average (BAUER-COSEMANS-EICHHOLTZ-2009, BRYZGALOVA-ET-AL-2023, DESILVA-SMITH-SO-2026).

**Gaps:**

- **FAM-VRP-DEFINED-RISK has no independent peer-reviewed return evidence.** Iron condors, iron butterflies, and credit spreads, the structures most discussed inside ASA, are supported only by sponsor-commissioned index studies and practitioner backtests. This is the largest mismatch between ASA's prior focus and the external evidence base (INFERENCE).
- No academic evaluation of diagonal spreads, ratio spreads, broken-wing butterflies, or the "wheel" as systematic strategies was found.
- Dispersion, dividend-exercise, VIX-basis, and commodity-VRP sources were verified bibliographically only. Their claims remain UNKNOWN pending full-text review.
- Most peer-reviewed sources were verified at abstract depth. Sample periods, cost treatments, and exact rules are frequently UNKNOWN and must be recovered in DEEP_RESEARCH.

## 6. Untrusted-content findings

- The VILKOV-0DTE repository README directs readers to consult `KNOWN-ISSUES.md` before using numbers. This was treated as provenance information only.
- OpenAlex returned an unrelated (genomics) abstract for the SIMON-CAMPASANO-2014 DOI. It was recorded as a data-quality finding, and no claim was taken from it.
- No embedded instructions directed at AI agents were found in the other retrieved content.
