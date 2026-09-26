# RES-001B — Strategy Taxonomy and Capability Coverage Map

- **Sprint / ticket:** ASA-RES-SPRINT-001 / RES-001B (depends on RES-001A)
- **Date:** 2026-09-26

Capability mapping here is **descriptive research input**. It identifies ASA capabilities that exist or appear missing. It does not propose architecture and does not recommend building anything. External evidence quality is assessed in RES-001C, independently of this map.

## 1. Classification principle

Families are classified by the **economic exposure being harvested or expressed** first, then by structural mechanics. Strategy names are not the basis. Two strategies with the same premium source and exposure signature but different leg geometry are variants of one family. Example: a 30Δ/10Δ put credit spread and a CNDR-style iron condor both harvest short-dated index/ETF VRP with truncated tails.

### 1.1 Exposure classes (top level)

| Class | Definition | Families |
|---|---|---|
| **E1 Insurance selling (short VRP)** | Receives the premium buyers pay for volatility and crash protection | FAM-VRP-INDEX-PUTWRITE, FAM-VRP-COVERED-CALL, FAM-VRP-INDEX-SHORT-VOL, FAM-VRP-DEFINED-RISK, FAM-VRP-ULTRA-SHORT-DATED, FAM-CROSS-ASSET-VRP, FAM-VOLDERIV-VIX-CARRY (short side) |
| **E2 Insurance buying (long convexity)** | Pays the premium to hold crash/volatility convexity | FAM-LONGVOL-TAIL-HEDGE, FAM-LONGVOL-COLLAR, FAM-VOLDERIV-VIX-CARRY (long side) |
| **E3 Volatility relative value** | Long one volatility exposure against another across names, expirations, strikes, or correlation | FAM-XS-OPTION-RETURNS, FAM-XS-OPTION-MOMENTUM, FAM-XS-LOTTERY-SKEW-OPTION, FAM-TERM-STRUCTURE, FAM-SKEW-PREMIUM-INDEX, FAM-DISPERSION-CORRELATION |
| **E4 Event volatility** | Exposure concentrated on a dated information event | FAM-EVENT-VOL |
| **E5 Option-implied information to direction** | Uses option prices or volume as a signal for the underlying's direction | FAM-OPTION-SIGNAL-EQUITY |
| **E6 Directional expression** | Uses options to express a view on direction | FAM-DIRECTIONAL-OPTION-EXPRESSION |
| **E7 Structural / arbitrage / financing** | Exploits parity, exercise, or financing frictions; no volatility or direction premium | FAM-ARBITRAGE-PARITY |

A strategy can combine classes. ASA's Skew Momentum is an E5 signal delivered by an E6 expression, with E3 (IV-RV) conditioning components. Hybrids are classified by each component, so evidence for one component is never silently credited to the combination.

## 2. Family × dimension map

Codes:
- **Direction:** `+` long delta, `−` short delta, `0` neutral, `±` signal-dependent.
- **Volatility / theta / skew / term / event:** `S` short, `L` long, `RV` relative value, `–` negligible.
- **Risk:** `D` defined, `U` undefined, `D*` defined per position but path-/margin-dependent.
- **Management:** `L` low (hold to expiry / mechanical roll), `M` medium (rules-based exits/rolls), `H` high (dynamic hedging or frequent rebalance).

"Typical" means as documented in the family's cited sources. Where the sources do not specify, the cell is `UNKNOWN`.

| Family | Dir | Vol | Theta | Skew | Term | Event | Risk | Legs | Strikes | Expiries | Payoff | Entry signal | Mgmt | Horizon | Data dependencies |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VRP-INDEX-PUTWRITE | + | S | + | S | front | – | U (cash-secured) | 1 (+cash) | 1 | 1 | asym | calendar (none) | L | 1 wk–1 mo | index chain, T-bill |
| VRP-COVERED-CALL | + | S | + | – | front | – | U (stock loss) | 1 + stock | 1 | 1 | asym | calendar (none) | L | 1 mo | chain, underlying |
| VRP-INDEX-SHORT-VOL | 0 | S | + | S | front | – | U | 2 (± hedge) | 1–2 | 1 | sym | none / VRP level | M–H if hedged | days–1 mo | chain, RV, hedging |
| VRP-DEFINED-RISK | 0/+ | S | + | S (put side) | front | – | D | 2–4 | 2–4 | 1 | sym (condor/fly) / asym (vertical) | calendar (none) | L–M | 1–2 mo | chain, delta |
| VRP-ULTRA-SHORT-DATED | 0 | S | + | S | 0–7 DTE | intraday | D or U | 1–4 | 1–4 | 1 | varies | intraday timing | H | intraday–1 wk | intraday chain, SPX |
| LONGVOL-TAIL-HEDGE | − (tail) | L | − | L | front–mid | – | D (premium) | 1 (+ stock) | 1 | 1 | asym | none / timing | L–M | 1–3 mo | chain |
| LONGVOL-COLLAR | + (bounded) | ± | ± | L | front | – | D | 2 + stock | 2 | 1 | asym | none / conditioning | L–M | 1–3 mo | chain, underlying |
| VOLDERIV-VIX-CARRY | 0 (≈ − equity) | S/L | + (short) | – | RV (roll) | – | U (short) | 1–2 futures | n/a | 1–2 | asym | term slope | M | 1 mo roll | VIX futures, VIX |
| TERM-STRUCTURE | 0 | RV | RV | – | RV | possible | D (calendar) / U | 2 (+) | 1 | 2 | asym | slope / forward vol | M | 1–3 mo | multi-expiry chain, earnings dates |
| XS-OPTION-RETURNS | 0 (hedged) | RV | ± | ± | – | – | U (portfolio) | many | 1/name | 1 | portfolio | cross-sectional rank | H | 1 mo | historical option panel, RV, characteristics |
| XS-OPTION-MOMENTUM | 0 | RV | ± | – | – | seasonal | U (portfolio) | many | 1–2/name | 1 | portfolio | past straddle returns | H | 1 mo | 6–36 mo option-return history |
| XS-LOTTERY-SKEW-OPTION | 0/± | RV | ± | RV | – | – | U (portfolio) | many | 1–2/name | 1 | portfolio | skewness / leverage rank | H | 1 wk–1 mo | option panel, RN moments, retail flow |
| EVENT-VOL | 0 | L or S | ± | – | RV (event vs non-event expiry) | L/S | D (straddle long) / U (short) | 2 | 1 | 1–2 | sym | event date | M | days | earnings calendar, chain across the event |
| OPTION-SIGNAL-EQUITY | ± | – (signal only) | – | signal | – | possible | depends on expression | expression | expression | expression | expression | smirk/IV spread/RNS/volume | M | 1 wk–6 mo | chain history, volume, borrow fees |
| SKEW-PREMIUM-INDEX | 0 (delta-hedged) | RV | ± | S | – | – | U | 2 + hedge | 2 | 1 | asym | skew level | H | 1 mo | chain, RN moments |
| DISPERSION-CORRELATION | 0 | RV (short index / long single) | ± | – | – | – | U | many | many | 1 | portfolio | implied vs realized correlation | H | 1 mo | index + constituent chains, weights |
| ARBITRAGE-PARITY | 0 | – | – | – | – | ex-dividend | D (box) | 2–4 | 1–2 | 1 | fixed | parity violation / dividend date | M | days–months | chain, dividends, rates, borrow |
| CROSS-ASSET-VRP | 0/+ | S | + | S | front | – | U | 1–2 | 1–2 | 1 | varies | none | L–M | 1 mo | non-equity option data |
| DIRECTIONAL-OPTION-EXPRESSION | ± | L (long premium) | − | varies | – | possible | D | 1–2 | 1–2 | 1 | asym | external directional signal | L–M | days–months | chain + signal |

## 3. Structural primitive map

Named practitioner structures reduce to a small set of reusable **structure primitives** (Pxx) and **analytic primitives** (Axx). A structure that adds no new primitive is a **cosmetic variant**.

### 3.1 Structure primitives

| ID | Primitive | Geometry | Families using it |
|---|---|---|---|
| P01 | single option leg | 1 strike, 1 expiry | PUTWRITE, TAIL-HEDGE, DIRECTIONAL, CROSS-ASSET-VRP |
| P02 | vertical | 2 strikes, same expiry, same type | DEFINED-RISK, DIRECTIONAL, (Skew Momentum expression) |
| P03 | straddle | same strike, same expiry, call + put | SHORT-VOL, EVENT-VOL, XS-OPTION-MOMENTUM, XS-OPTION-RETURNS |
| P04 | strangle | 2 strikes, same expiry, call + put | SHORT-VOL, ULTRA-SHORT-DATED |
| P05 | four-leg wing combination | two verticals (iron condor / iron butterfly) | DEFINED-RISK, ULTRA-SHORT-DATED |
| P06 | calendar | same strike, 2 expiries | TERM-STRUCTURE, EVENT-VOL |
| P07 | diagonal | 2 strikes, 2 expiries | TERM-STRUCTURE (variant) |
| P08 | ratio / unequal-quantity combination | unequal leg quantities | ULTRA-SHORT-DATED (studied), SKEW-PREMIUM |
| P09 | stock + option overlay | underlying with short call / long put / both | COVERED-CALL, TAIL-HEDGE, COLLAR |
| P10 | delta-hedged option | option + dynamic underlying hedge | SHORT-VOL, XS-OPTION-RETURNS, SKEW-PREMIUM, DISPERSION |
| P11 | option-strip replication | strike continuum approximating variance / moment swaps | SHORT-VOL (variance), SKEW-PREMIUM (skew swaps), TERM-STRUCTURE |
| P12 | cross-sectional structure portfolio | the same structure across many underlyings, periodically rebalanced | XS-OPTION-RETURNS, XS-OPTION-MOMENTUM, XS-LOTTERY-SKEW-OPTION |
| P13 | multi-underlying linked position | index options against constituent options | DISPERSION-CORRELATION |
| P14 | volatility futures position | VIX futures / ETP | VIX-CARRY |
| P15 | box / synthetic | 4 legs replicating a riskless or synthetic payoff | ARBITRAGE-PARITY |

**Cosmetic variants (INFERENCE):** these add no primitive beyond the ones listed.

- jade lizard = P02 + P01;
- broken-wing butterfly = P05 with asymmetric widths;
- "wheel" = alternating P01 (cash-secured put) and P09 (covered call);
- poor-man's covered call = P07;
- 1x2 ratio = P08;
- risk reversal = P01 + P01 (opposite types).

They may still differ materially in *risk shape*, but not in the capability they require.

### 3.2 Analytic primitives

| ID | Analytic primitive | Required by |
|---|---|---|
| A01 | per-contract IV and greeks | nearly all |
| A02 | delta-targeted strike selection | PUTWRITE (variants), DEFINED-RISK, COVERED-CALL (variants) |
| A03 | realized volatility | SHORT-VOL, XS-OPTION-RETURNS, OPTION-SIGNAL |
| A04 | IV − RV spread / VRP level | XS-OPTION-RETURNS, SHORT-VOL conditioning |
| A05 | IV term-structure slope / implied forward volatility | TERM-STRUCTURE, VIX-CARRY, EVENT-VOL |
| A06 | skew / smirk level and history | OPTION-SIGNAL, SKEW-PREMIUM |
| A07 | model-free risk-neutral moments (variance, skewness, kurtosis) | OPTION-SIGNAL (RNS), XS-LOTTERY-SKEW, SKEW-PREMIUM, SHORT-VOL (variance) |
| A08 | historical option-price panel (returns of options through time) | every cross-sectional family; any external replication |
| A09 | event calendar and expected event move | EVENT-VOL, TERM-STRUCTURE (event contamination) |
| A10 | borrow fee / short-sale constraint | OPTION-SIGNAL (post-2025 evidence), XS-OPTION-RETURNS (Ramachandran-Tayal) |
| A11 | signed or open/close option volume | OPTION-SIGNAL (Pan-Poteshman, O/S), XS-OPTION-RETURNS (order flow) |
| A12 | option liquidity and effective-spread measurement | all (cost sensitivity), XS-OPTION-RETURNS (illiquidity premium) |
| A13 | cross-sectional ranking across a universe | all XS families, OPTION-SIGNAL |
| A14 | dynamic delta-hedge simulation / execution | P10 families |
| A15 | margin and capital model | PUTWRITE, SHORT-VOL, VIX-CARRY (Santa-Clara–Saretto frictions) |
| A16 | index weights and implied correlation | DISPERSION-CORRELATION |
| A17 | option-return history per name (6–36 months) | XS-OPTION-MOMENTUM |

## 4. ASA capability coverage map (descriptive)

This section is based on the repository at `main` @ a4f58b7. "Apparent" means the Researcher's reading of code and contracts. The owning roles have not confirmed it.

### 4.1 Apparent existing capabilities

| Capability | Evidence in repository |
|---|---|
| Real-time quote, historical underlying bars, option chain (with provider greeks/IV) | `market_data/tradier.py` (`REAL_TIME_QUOTE_V1`, `HISTORICAL_BARS_V1`, `OPTION_CHAIN_V1`) |
| Earnings calendar | `market_data/finnhub.py`, `market_data/alpha_vantage.py` (`EARNINGS_CALENDAR_V1`) |
| Trading calendar, corporate actions | `domain/market_data.py` (`TRADING_CALENDAR_V1`, `CORPORATE_ACTIONS_V1`) |
| Realized volatility, trailing return | `analytics/realized_volatility.py` |
| Implied forward volatility, forward factor, IV term-structure spread | `analytics/derived_facts.py`, `analytics/forward_factor.py` |
| ATM IV vs RV; call/put wing IV vs RV | `analytics/derived_facts.py` |
| Normalized call/put skew; skew historical z-score and percentile (prospectively accumulated) | `analytics/derived_facts.py`, `strategy_runtime/historical_evidence.py` |
| Cross-sectional and sector-relative momentum; cross-sectional ranking | `analytics/cross_sectional_ranking.py`, `analytics/derived_facts.py` |
| Option volume band, spread quality, open-interest quality | `analytics/derived_facts.py` |
| Days to earnings; earnings inside trade window | `analytics/derived_facts.py` |
| Delta-nearest leg selection; ATM and expiration selection | `analytics/option_selection.py`, `analytics/atm_selection.py`, `analytics/expiration_selection.py` |
| Structures in the strategy runtime: vertical, calendar (+custom) | `strategy_runtime/contract.py` `StructureKind` |
| Portfolio structure recognition: vertical, calendar, double calendar | `asa/contracts/portfolio_structures.py` |
| Domain vocabulary for single-leg, diagonal, straddle, strangle, covered call, cash-secured put | `domain/financial.py` `OptionStructureType` (vocabulary only; runtime support not confirmed) |

### 4.2 Primitive coverage

| Primitive | Apparent ASA state |
|---|---|
| P01 single leg | vocabulary only (INFERENCE: no runtime strategy uses it) |
| P02 vertical | **present** (SPY PCS, Skew Momentum) |
| P03 straddle / P04 strangle | vocabulary only. A prior Architect note says STRADDLE needs its own review (`project/reports/STRATEGY-LIBRARY-001-SL-02-SECOND-CANDIDATE-SEARCH.md`) |
| P05 iron condor / butterfly | apparently missing as a runtime structure |
| P06 calendar | **present** (forward factor, earnings calendar, double calendar) |
| P07 diagonal | vocabulary only |
| P08 ratio | apparently missing |
| P09 stock + option overlay | vocabulary only (covered call, CSP) |
| P10 delta-hedged option | apparently missing |
| P11 option-strip replication | apparently missing |
| P12 cross-sectional structure portfolio | partial: cross-sectional ranking exists, but no portfolio-of-structures construct was found |
| P13 multi-underlying linked | apparently missing |
| P14 volatility futures | apparently missing (no VIX capability) |
| P15 box / synthetic | apparently missing |
| A01, A02, A03 | present |
| A04 | present (ATM/wing IV vs RV) |
| A05 | present (term-structure spread, forward volatility) |
| A06 | present (skew level; history accumulated prospectively only) |
| A07 model-free RN moments | apparently missing |
| A08 historical option panel | **apparently missing.** No approved provider supplies historical option data (see `strategy_runtime/historical_evidence.py` docstring) |
| A09 event calendar | present (dates). Expected-move analytics not found |
| A10 borrow fee | apparently missing |
| A11 signed / open-close volume | missing (only a volume band) |
| A12 liquidity measurement | partial (spread quality, OI quality) |
| A13 cross-sectional ranking | present |
| A14 delta-hedge simulation | apparently missing |
| A15 margin/capital model | UNKNOWN (not investigated) |
| A16 index weights / implied correlation | apparently missing |
| A17 per-name option-return history | apparently missing (depends on A08) |
| SPX / index instruments | apparently missing (`InstrumentKind` has no INDEX; no settlement-root identity; see `project/reports/STRATEGY-LIBRARY-001-SL-02-CNDR-ARCHITECT-DECISION.md`) |

### 4.3 Capability-question answers per family (descriptive)

| Family | Needs new structure primitive? | Needs new analytics? | Needs new external data? | Reuses existing | Primitive would also unlock |
|---|---|---|---|---|---|
| VRP-INDEX-PUTWRITE | P01 (runtime) | A15 | SPX index instruments (if index-faithful); ETF variant uses existing chain | chain, delta, T-bill UNKNOWN | TAIL-HEDGE, DIRECTIONAL, CROSS-ASSET |
| VRP-COVERED-CALL | P09 | – | – | chain, quote | COLLAR, TAIL-HEDGE |
| VRP-INDEX-SHORT-VOL | P03/P04 (unhedged); P10 (hedged) | A14 | – (ETF); SPX (index) | chain, RV, IV-RV | EVENT-VOL, XS families (P03), SKEW-PREMIUM (P10) |
| VRP-DEFINED-RISK | P05 (condor/fly); P02 present | – | SPX for CNDR/BFLY fidelity | vertical, delta selection | ULTRA-SHORT-DATED |
| VRP-ULTRA-SHORT-DATED | P05, P03, P04 | intraday timing | intraday SPX 0DTE data | – | – |
| LONGVOL-TAIL-HEDGE | P01, P09 | – | – | chain | PUTWRITE |
| LONGVOL-COLLAR | P09 (3-leg) | – | – | chain | COVERED-CALL |
| VOLDERIV-VIX-CARRY | P14 | A05 on VIX curve | VIX futures | – | – |
| TERM-STRUCTURE | P06 present; P07 | A05 present | – | calendar, forward factor, earnings | EVENT-VOL |
| XS-OPTION-RETURNS | P10, P12 | A04 present; A12 partial; A14 | **A08 historical option panel** | cross-sectional ranking, IV-RV | XS-MOMENTUM, XS-LOTTERY, SKEW-PREMIUM |
| XS-OPTION-MOMENTUM | P03, P12 | A17 | **A08** | ranking | XS-OPTION-RETURNS |
| XS-LOTTERY-SKEW-OPTION | P01/P03, P12 | A07 | **A08**; retail-flow data (Choy) | ranking | OPTION-SIGNAL (A07) |
| EVENT-VOL | P03 (straddle), P06 present | expected move | – | earnings calendar, calendar structure | SHORT-VOL, XS families |
| OPTION-SIGNAL-EQUITY | expression-dependent (P02 present) | A06 present; A07; A10; A11 | borrow fees; signed volume; **A08** for history | skew, IV-RV, momentum | XS-LOTTERY (A07) |
| SKEW-PREMIUM-INDEX | P10, P11 | A07 | SPX | skew | SHORT-VOL (P11) |
| DISPERSION-CORRELATION | P13, P10 | A16 | index weights | – | – |
| ARBITRAGE-PARITY | P15 | rates, dividends | rate source | corporate actions | – |
| CROSS-ASSET-VRP | P01/P03 | – | non-equity option data | – | – |
| DIRECTIONAL-OPTION-EXPRESSION | P02 present; P01 | – | – | vertical | – |

**Highest-reuse missing primitives (DERIVED from the table above, by count of families unlocked):**

1. **A08 historical option-price panel.** It gates every cross-sectional family and any faithful external replication.
2. **P10 delta-hedged option / A14.** Gates SHORT-VOL (hedged), XS-OPTION-RETURNS, SKEW-PREMIUM, DISPERSION.
3. **P03 straddle / P04 strangle.** Gates SHORT-VOL, EVENT-VOL, and XS-OPTION-MOMENTUM.
4. **SPX index-instrument identity.** Gates index-faithful PUTWRITE, CNDR/BFLY, 0DTE, and SKEW-PREMIUM.

This count describes reuse. It does not recommend that any of them be built, and it does not bear on evidence quality.

## 5. Unresolved classification questions

1. **Covered call vs put write.** By put-call parity, BXM and PUT are near-equivalent exposures. They are kept as separate families because they are distinct predominant benchmarks with different capability needs (P09 vs P01). A downstream method must avoid counting their shared VRP evidence twice (RES-001D §5).
2. **Defined-risk vs index short-vol.** Whether truncated-tail structures preserve the VRP per unit of risk is an **open empirical question**. No independent source was found. They are kept separate so the evidence gap stays visible.
3. **Option-signal families with an option expression** (e.g., Skew Momentum). This is a hybrid of E5 and E6. The taxonomy classifies components. It does not decide whether hybrids deserve their own family.
4. **XS-OPTION-RETURNS vs XS-LOTTERY vs XS-MOMENTUM.** The HORENSTEIN-VASQUEZ-XIAO-2026 and GOYAL-SARETTO-2022-IPCA evidence suggests they share factors. The split follows the literature's own signal families. It may overstate independence.
5. **Ultra-short-dated as a separate family or a horizon variant of E1.** It is kept separate because it has distinct market structure (retail dominance, intraday execution) and distinct negative evidence.
6. **Margin/capital model (A15).** Whether ASA has one was not investigated. UNKNOWN.
