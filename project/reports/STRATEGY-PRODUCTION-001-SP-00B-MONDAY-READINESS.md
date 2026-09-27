# STRATEGY-PRODUCTION-001 SP-00B — Monday readiness and aggregate capacity baseline

- **Ticket:** SP-00B (depends on SP-00A, merged in #506)
- **Basis:** `main` @ `cf7e6ac`
- **Risk:** R1 (documentation)
- **Measurement method:**
  - Every metric below is **bounded from repository configuration and source timing rules**.
  - Nothing is claimed as a production measurement. Direct production API reads were not available to this worker in this session.
  - Measured values are owned by SP-07B (pre-release, production-equivalent cycle) and SP-08A (real session).

## 1. Monday 2026-09-28 per-strategy state

Today none of the seven is in the production registry. The column below is the **expected post-release state** for that session under the source timing rules. It applies only if the strategy has shipped and been deployed by then. Deployment is Founder-only (SP-08A).

| Strategy | Source due rule | Due on Mon 2026-09-28? | Expected state | Why |
|---|---|---|---|---|
| `event_vol_gxz_preea_straddle_to_expiry` | close of session(day0, −3) | Only for subjects whose earnings day0 = session +3 (Thu 2026-10-01) | **LIVE_EVALUABLE** for those subjects; **NOT_DUE** otherwise | Uses existing `EARNINGS_CALENDAR_V1` + `OPTION_CHAIN_V1`. Provider delta (not OptionMetrics) is disclosed as PROVIDER uncertainty, not blocked. |
| `index_putwrite_cboe_put` | roll date = third Friday (2026-10-16) | No | **NOT_DUE** | Graph evaluates the roll gate FAIL → NO_ACTION |
| `index_putwrite_cboe_puty` | same as PUT | No | **NOT_DUE** | same as PUT |
| `index_buywrite_cboe_bxm` | same roll date | No | **NOT_DUE** | same as PUT |
| `index_short_vol_scs_near_atm_straddle` | close of first trading day of month (2026-10-01) | No | **NOT_DUE** | |
| `xs_option_zhan_neg_lnprice_dn_call` | close of last trading day of month (2026-09-30) | No | **NOT_DUE** | |
| `xs_option_heston_straddle_momentum_lowcost` | monthly expiration day (2026-10-16) | No | **NOT_DUE**; when due, **LIVE_TYPED_DATA_BLOCKER** | Needs 11 complete monthly straddle returns (lags 2–12) from a point-in-time panel (A08). No such panel exists and none is synthesized, so it will be typed UNKNOWN until real history accrues. |

A due date that falls in the same week as the first release gives an earlier real observation:
- Zhan on Wed 2026-09-30;
- SCS on Thu 2026-10-01;
- GXZ daily.

The **no unproven full-evaluability claim** holds:
- only GXZ is claimed evaluable on Monday, and only for earnings-qualified subjects;
- every other strategy is NOT_DUE by source rule, not by assumption.

## 2. Capacity baseline (bounded)

### Current production shape (from code)

| Item | Value | Source |
|---|---|---|
| Scheduler cadence | `*/10 13-20 * * 1-5` UTC. Session slots run from open+10 min to close−10 min. | `railway.cron.json`, `market_data/session_schedule.py:41-42` |
| S&P cohort per cycle | 30 subjects × {forward_factor, skew_momentum, earnings_calendar} | `asa/scheduled_screening.py` (`SP500_COHORT_MAXIMUM_SUBJECTS`) |
| Fixed-subject pairs | B001/SPY, B002/SPY, spy_put_credit_spread/SPY | `SCHEDULED_FIXED_SUBJECT_PAIRS` |
| Tradier documented limit | 120 requests/min (production) | `market_data/tradier.py:76` |
| Subject-level demand sharing | Identical `CapabilityDemand.demand_id` is fetched once per subject | `domain/capability_demand.py:89`, `market_data/capability_coalescing.py` |

### Required-request bounds per due evaluation

| Capability | Current cycle (≤30 cohort subjects) | GXZ | PUT/PUTY/BXM (shared) | SCS | Zhan (formation day) | Heston (formation day) |
|---|---|---|---|---|---|---|
| quote | ≤30 (+1 SPY) | ≤1 per EA subject | 1 INDEX (SPX) | same SPX quote | ≤~500 | ≤~500 |
| option expirations | ≤30 (+1) | ≤1 per EA subject | 1 (SPX) | same | ≤~500 | ≤~500 |
| option chain | ≤~90 (≤3 expirations/subject) | ≤2 per EA subject | 1 (next monthly SPX) | 1 (~45 DTE SPX) | ≤~500 | ≤~500 |
| historical option panel | 0 | 0 | 0 | 0 | 0 | ≤~500 (ASA-persisted reads, not provider requests) |
| trade tape | 0 | 0 | ≤3 (one per contract, outcome valuation only) | 0 | 0 | 0 |
| rate | 0 | 0 | 1 (shared T-bill 4w/13w) | 1 (shared risk-free) | 1 (shared) | 0 |
| security master | 0 | 0 | 0 | 0 | ≤~500 | ≤~500 (shared with Zhan) |
| earnings | ≤30 | from shared calendar | 0 | 0 | 0 | 0 |

- **Expected due strategy-subject pairs on Monday:** the existing ≤93 plus GXZ EA-qualified subjects, bounded by the earnings calendar. The six NOT_DUE strategies each add only their date-gate evaluation (≤1 pair each).
- **Current cycle duration:**
  - not measured here;
  - lower bound for 30 subjects ≈ ⌈(30 quotes + 30 expirations + ~90 chains) / 120⌉ ≈ 2 min of Tradier budget per cycle.
- **Current provider deferrals:** not measured here. They are recorded per pair by the existing budget/rolling-window exhaustion typing (`market_data/budget.py`).

### Capacity risks and owners

| Risk | Specific owner |
|---|---|
| Zhan/Heston monthly formation needs the whole S&P universe (~1,500–2,000 provider requests at 120/min ≈ 13–17 min of budget) inside one formation session. RA-XS-01 needs full-universe breakpoints. | SP-07B. The plan is a generic typed capacity deferral plus a multi-cycle formation-day acquisition plan. Partial universes produce UNKNOWN breakpoints, never a ranking over a truncated set. |
| Close-of-day entries (GXZ, SCS, Zhan) against a schedule that ends at close−10 min | SP-07A. The scheduler has to model an event/close observation path, never shifting the source time silently. |
| SPX chain fetched by four strategies | Shared demand. PUT, PUTY and BXM share one next-monthly SPX chain demand (identical `demand_id`). SCS has a different expiration. |

### Shared-acquisition reuse opportunities (identified)

1. Next-monthly SPX chain and SPX INDEX quote: PUT, PUTY, BXM (one demand each).
2. Rates observation: PUT, PUTY, SCS, Zhan (one per effective date).
3. Equity quote/expirations/chains: Zhan, Heston and the existing cohort strategies share per-subject demands on overlapping subjects.
4. Security master: Zhan and Heston.
5. The earnings calendar is already shared by earnings_calendar and GXZ.

Cross-subject deduplication of identical demands is SP-07B's scope. Today, sharing is per subject only.

## 3. Acceptance

- `no_unproven_full_evaluability_claim`: §1.
- `capacity_risk_has_specific_owner`: §2, risks table.
- `current_shared_acquisition_reuse_opportunities_identified`: §2, reuse list.
