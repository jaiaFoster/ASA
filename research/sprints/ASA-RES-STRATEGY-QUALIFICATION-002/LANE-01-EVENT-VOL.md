# Lane 1 — Event volatility: candidate survey and qualification

**Result:** **0 of 2** primaries reached READY status. Two primaries are specified at DEEP_RESEARCH_REQUIRED, and one alternate is rejected.

## Candidates

| Candidate | Source (depth) | Role | State |
|---|---|---|---|
| [GXZ pre-announcement straddle, hold to expiry](strategy-specifications/ASA-QS-EV-01-GXZ-PREEA-STRADDLE-TO-EXPIRY.md) | GAO-XING-ZHANG-2013-WP (full text; published 2018 version not accessible) | PRIMARY | DEEP_RESEARCH_REQUIRED |
| [ALX concavity-conditioned EAD straddle](strategy-specifications/ASA-QS-EV-02-ALX-CONCAVE-EA-STRADDLE.md) | ALEXIOU-ET-AL-2025 (publisher full text) | PRIMARY | DEEP_RESEARCH_REQUIRED |
| [GXZ delta-neutral straddle, day −3 to day 0](strategy-specifications/ASA-QS-EV-A1-GXZ-DN-STRADDLE-M3-0.md) | GAO-XING-ZHANG-2013-WP | ALTERNATE | RESEARCH_REJECT |

**Surveyed but not specified:**

| Source | Reason |
|---|---|
| BARTH-SO-2014 (preprint full text) | Measures non-diversifiable volatility risk at announcements. Defines no straddle trading rule. |
| ALX JUMPSTRADDLE (delta- and vega-neutral calendar) | A second construction in the same paper, reported as a conditional differential only: CONCAVE −10.69% vs 2.29%. It shares ALX's direction and universe blockers, so it is not a separate candidate. |
| Practitioner "IV crush" material | Discovery only. Not explicit enough to reproduce. |
| Event term-structure / calendar rule | ASA's existing forward-factor earnings calendar is prior internal work; no new independently sourced event-calendar rule with full-text evidence was recovered in this sprint. |

## Lane-specific mathematics

| Requirement | GXZ (EV-01) | ALX (EV-02) |
|---|---|---|
| Event time | day 0 = I/B/E/S date; no after-close adjustment in the preprint | EAD = next trading day if the announcement is after the close (DF-EA-EFFECTIVE-DATE-ALX) |
| Event vs non-event expiration | expiration must be after day 0 ("constructed before … expires after") | shortest expiry 4–13 calendar days, which spans the EAD by construction |
| Expected-move definition | not used | not used; CONCAVE is a curve-shape indicator, not an expected move. A09 is **not** consumed by either source. |
| Pre/post timing | enter at the close of session −3; hold to expiry | enter at the close of d−1; exit at the close of d |
| Volatility change vs realized move | hold-to-expiry payoff is the realized move (intrinsic value); the [−3,0] alternate captures the implied-volatility run-up | one-day return mixes the IV crush and the realized move; the paper decomposes it with the JUMPSTRADDLE and VOLSTRADDLE constructions |
| Exit relative to the announcement | after (at expiry) | after (close of the EAD) |
| Cost sensitivity | Table 6: at 100% of quoted spread, only the 4–10-day group is positive (0.61%/day, t 2.08) | differential robust to costs; levels "substantially lower", not reported |

## Why fewer than two

The requirement is that "if two strategies cannot honestly reach implementation-ready research status, return fewer and state exactly why".

**GXZ (EV-01).** The accessible preprint leaves three signal- or structure-level rules undefined for the hold-to-expiry variant:
1. The DTE unit, and a conflict between the [4, 10] group and the paper's own 10–60-day filter.
2. Whether Table 6 straddles are delta-neutral.
3. How multiple qualifying pairs are volume-weighted.

The published JFQA 2018 text may resolve these, but it was not accessible.

**ALX (EV-02).** Three problems:
1. The universe is look-ahead: the same calendar year's option-volume ranking.
2. The paper reports a conditional return differential but authors no trade direction.
3. Net level returns are not reported.

**Alternate (EV-A1).** Rejected on the authors' own net-of-spread arithmetic, about −8% for the 3-day round trip at a 50% effective spread.

## Evidence uncertainties

- **Era dependence.** GXZ (1996–2010) find positive pre-announcement straddle returns. ALX (2013–2020, liquid names) find a negative unconditional EAD mean of −0.86%, with a median of −15.43%.
- **Persistence.** No post-2010 test of the GXZ hold-to-expiry rule was recovered.
- **Costs.** Around announcements, relative spreads in the GXZ sample were about 14–16%.
