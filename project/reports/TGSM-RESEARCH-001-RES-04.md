# TGSM-RESEARCH-001 — RES-04 production-logic reuse

Historical research now has one deliberately thin seam:
`strategy_runtime.tgsm_research.evaluate_tgsm_research_target`. It accepts already
sealed cohort knowledge and delegates interpretation to
`evaluate_s001_cohort`, then delegates allocation to
`build_s001_target_decision`. Both are the production S001 authorities.

A deterministic fixture proves the universal runtime and research seam produce
the exact same immutable target decision and identity for the same eligible
inputs. No second TGSM implementation, provider access, market-data authority,
or alternate allocation logic exists. RES-01's `DATA_LIMITED` result continues
to prohibit result-bearing historical execution.
