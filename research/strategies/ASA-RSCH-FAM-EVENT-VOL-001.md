# ASA-RSCH-FAM-EVENT-VOL-001 — Event Volatility (earnings and scheduled events)

## Identity

- **Research ID:** ASA-RSCH-FAM-EVENT-VOL-001
- **Strategy:** Event Volatility (earnings and scheduled events)
- **Family:** FAM-EVENT-VOL (E4 event volatility); taxonomy in `research/sprints/ASA-RES-SPRINT-001/RES-001B-taxonomy.md`
- **Research status:** TRIAGE
- **Created:** 2026-09-26
- **Updated:** 2026-09-26

This is a family-level comparable record (RES-001C). Status describes evidence only. It is not a priority, selection, or implementation signal. Numeric values are stated only where a source reports them; everything else is UNKNOWN. Claim classes: REPORTED / DERIVED / INFERENCE / UNKNOWN. Source verification depth for this record: bibliographic_and_abstract: 5, bibliographic_and_search_engine_summary: 1.

## Thesis

### Concise description

Trade volatility around dated information events: long straddles into earnings, short volatility after, event-spanning calendars, or options spanning political events.

### Proposed economic or behavioral mechanism

Announcement uncertainty is priced and large (DUBINSKY-ET-AL-2019); investors may underestimate it for noisy, costly-to-trade firms (GAO-XING-ZHANG-2018), while bellwether announcements carry non-diversifiable risk premia (BARTH-SO-2014); retail overpays (DESILVA-SMITH-SO-2026).

## Evidence

Sample, universe and method context: US single-stock options around quarterly earnings; international indexes around political events.

### Original research

- **GAO-XING-ZHANG-2018** — ATM straddles from 3 days before to the announcement earn 3.34% on average; larger for small, volatile, illiquid firms.

### Supporting research

- **DUBINSKY-ET-AL-2019** — Anticipated announcement uncertainty large and informative.
- **HESTON-ET-AL-2026** — Quarterly variance seasonality tied to earnings revisions.
- **KELLY-PASTOR-VERONESI-2016** — Options spanning political events more expensive.

### Independent replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Failed replications

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Contradictory research

- **BARTH-SO-2014** — Buyers pay a volatility risk premium for bellwether announcements (predictable straddle return variation) - opposite sign for that subset (DERIVED).
- **DESILVA-SMITH-SO-2026** — Retail buyers of pre-announcement options lose 5-9% (10-14% high-volatility), overpaying vs realized volatility.

### Post-publication evidence

- None found in this sprint's search coverage (see `research/sprints/ASA-RES-SPRINT-001/RES-001A-landscape.md` §2).

### Reported empirical results

| Field | Value |
|---|---|
| Reported return metrics | REPORTED: +3.34% per event window [-3,0] (GAO-XING-ZHANG-2018); retail -5 to -9% (DESILVA-SMITH-SO-2026, search depth). |
| Reported risk metrics | UNKNOWN. |
| Drawdown / tail | Long straddle: defined; short event vol: undefined gap exposure. |
| Opportunity frequency | Quarterly per name; many events per month across a universe. |
| Regime dependence | UNKNOWN. |
| Persistence | UNKNOWN. |
| Transaction-cost sensitivity | REPORTED: GXZ effect larger where costs higher; retail losses driven partly by spreads. |

## Specification

As documented in the sources. No rule is invented, and missing parameters are UNKNOWN.

| Field | Value |
|---|---|
| Entry rules | Earnings date - 3 trading days (GXZ). |
| DTE / expiration | Nearest expiry after the event (UNKNOWN exact in abstract). |
| Strike / delta | ATM. |
| Liquidity requirements | Effect strongest in less liquid names (REPORTED). |
| Exit rules | At announcement date (GXZ). |
| Roll rules | n/a (event). |
| Sizing assumptions | UNKNOWN. |
| Exclusions | UNKNOWN. |
| Unresolved rule gaps | Expiry selection, exact exit timing (pre/post announcement), cost treatment not recovered at abstract depth; prior ASA search recovered more detail (project/reports/STRATEGY-LIBRARY-001-SL-02-SECOND-CANDIDATE-SEARCH.md, internal). |

## Practical evidence

| Risk field | Value |
|---|---|
| Maximum / tail risk | Premium (long) / undefined (short). |
| Liquidity risk | High where effect is largest. |
| Assignment / exercise risk | Short legs through event (INFERENCE). |
| Gap risk | Central to the family. |
| Volatility-regime risk | Event-specific. |
| Model dependency | Medium. |
| Crowding / decay evidence | Retail crowding documented. |
| Known failure modes | Date errors; illiquid spreads consuming the premium. |

## Adversarial review

| Question | Answer |
|---|---|
| Replicated? | No direct replication of GXZ found. |
| Failed? | None found. |
| Later research? | Retail and bellwether evidence complicate sign. |
| Persisted? | UNKNOWN. |
| Data mining? | Window choice [-3,0] moderate risk. |
| Concentrated? | Small illiquid firms. |
| Parameter-dependent? | Window-dependent (INFERENCE). |
| Costs? | Could erase effect where it is largest. |
| Execution? | UNKNOWN. |
| Another factor? | Event variance premium. |
| Look-ahead? | Requires confirmed dates ex ante. |
| Failure regime? | Low-surprise quarters. |
| Crowding? | Retail. |
| Omission risk? | Omitting cost concentration. |

## ASA capability mapping

Performed after the external evidence assessment above. Implementation ease does not affect the evidence rating.

| Field | Value |
|---|---|
| Required market data | Chain; confirmed earnings date and timing (BMO/AMC). |
| Required analytics | A09 expected move; event-vs-diffusive variance separation. |
| Required history | Historical options around events. |
| Required event data | **Earnings calendar with confirmed dates.** |
| Structural primitives (RES-001B §3) | P03, P06. |
| Apparent existing ASA capabilities | Earnings calendar capability; days-to-earnings and earnings-inside-window facts; calendar/double-calendar structures (earnings calendar strategy exists). |
| Apparent missing ASA capabilities | Straddle structure (Architect review previously noted); historical option panel; expected-move analytics. |
| Execution complexity | Medium. |

## Assessment

### Strongest supporting evidence

Peer-reviewed positive pre-announcement straddle returns (GAO-XING-ZHANG-2018) with mechanism support (DUBINSKY-ET-AL-2019).

### Strongest contradictory evidence

Opposite-sign evidence for buyers in bellwethers and retail flow (BARTH-SO-2014, DESILVA-SMITH-SO-2026).

### Unresolved questions

- Net-of-cost GXZ returns
- Reconciliation of sign across subsets
- Evidence for event calendars (ASA earnings calendar) specifically

### Evidence limitations

Most sources were verified at bibliographic-and-abstract depth. Sample periods, cost models, and exact rules are often UNKNOWN until full texts are recovered.

### Qualification status

TRIAGE

### Qualification basis

TRIAGE: peer-reviewed, rule-explicit core result with material contradictory and cost evidence.

## Research history

- 2026-09-26: record created as TRIAGE in ASA-RES-SPRINT-001 (RES-001C). No prior conclusion existed.

## Provenance

- `research/sources/GAO-XING-ZHANG-2018.yaml`
- `research/sources/DUBINSKY-ET-AL-2019.yaml`
- `research/sources/HESTON-ET-AL-2026.yaml`
- `research/sources/KELLY-PASTOR-VERONESI-2016.yaml`
- `research/sources/BARTH-SO-2014.yaml`
- `research/sources/DESILVA-SMITH-SO-2026.yaml`
