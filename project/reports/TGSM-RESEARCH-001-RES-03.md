# TGSM-RESEARCH-001 — RES-03 experiment contract

`simulation/research_experiment.py` is the minimal immutable experiment and
result-identity contract. It records the strategy/version/checksum, sealed
evidence and universe identities, named formula versions, parameters, period,
temporal convention, defensive representation, transaction-cost assumption,
benchmark, code SHA, and preregistration identity. Canonical serialization
verifies its content-derived identity on provider-free replay. Result identity
covers the experiment, immutable return-series identity, and exact metric
values.

This is not a backtester or generalized research platform. It owns no market
data, provider, S001 interpretation, accounting algorithm, or result. RES-01's
`DATA_LIMITED` gate remains binding, so no result-bearing experiment has been
executed.
