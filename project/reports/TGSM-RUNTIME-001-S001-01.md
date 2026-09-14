# TGSM-RUNTIME-001 — S001-01 preserve and audit

Baseline: `main@91da4906d4746e096e9ac139eab11dd2b0aa383a`.

## Reuse-gap matrix

| Requirement | Classification | Existing owner / smallest gap |
| --- | --- | --- |
| Point-in-time universe membership | EXTEND | `screening.universe_membership` owns immutable effective snapshots; add generic effective intervals and a sector-ETF snapshot without historical ticker branching. |
| Instrument inception/eligibility | NEW | No eligibility interval exists; add it to the universe-member boundary, not S001 runtime. |
| Trading calendar/month-end semantics | EXTEND | B002 already owns completed-month selection; add a minimal injected next-session calendar function rather than a scheduler. |
| Adjusted/total-return evidence | EXTEND | `OHLCVBar.adjusted_close_basis` distinguishes split-only from split-and-dividend; S001 must accept only total-return-capable evidence. No raw fallback. |
| Trailing 12M total-return fact | NEW | Add one generic named/versioned analytics fact over canonical total-return-capable observations. |
| Completed-period SMA10M | REUSE | `sma_10m_completed_months@1.0.0`; inputs must have the required total-return-capable basis. |
| Cross-sectional snapshot/ranking | EXTEND | Cross-subject materialization exists; add generic deterministic value ranking that preserves missing subjects separately. |
| Eligibility/gating | NEW | Add pure generic typed eligibility/trend projections; S001 retains the `>` policy. |
| Target allocations | EXTEND | Existing immutable allocation vocabulary is opportunity-oriented; add a bounded research target-decision contract without broker/order semantics. |
| Defensive representation | NEW | Add one canonical research identity/fact input for three-month Treasury total return; do not invent an acquisition source or proxy. |
| Temporal availability/effective-after | EXTEND | Existing effective/evidence times are reusable; add injected next-eligible-session projection. |
| Decision provenance | REUSE | Existing canonical/derived evidence identities and deterministic serialization. |
| Persistence/replay | EXTEND | Existing immutable provider-free replay patterns; persist/replay the S001 decision value without live acquisition. |

## Architecture conclusion

The existing `StrategyContract` can express S001 with `StructureKind.NONE`, no
lifecycle, historical-bars market data, and custom named-fact requirements. The
generic subject-first and cross-subject seams can be extended without a
strategy-ID runtime branch or a parallel provider/analytics/universe system.

The total-return and defensive-source questions are fail-closed data-availability
boundaries, not permission to weaken S001. Fixtures can prove the runtime with
canonical facts. Production evaluability remains dependent on an entitled
split-and-dividend-adjusted history source and an authorized canonical Treasury
total-return source; those limitations must remain typed and explicit.

## Recovery

All S001 additions are additive. Reversion removes S001 registration and its new
generic fact/decision consumers; B001/B002 and existing option strategies retain
their contracts and paths.
